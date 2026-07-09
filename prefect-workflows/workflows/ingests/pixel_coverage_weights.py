"""This will consist of two flows.

The first flow will calculate pixel coverage weights for a given grid and polygon layer using exactextract.
    - Inputs
        - Grid layer (raster): Read a single timestep from an Icechunk repo.
        - Polygon layer (vector): This must pre-exist somewhere (in the locations table?) 
            - Have an upload feature (ev.locations.load?)
    - Outputs
        - Pixel coverage weights: Write to the iceberg warehouse table.
    - Approach
        - Domain name defines the unique grid (ie, "nwm30_puertorico_forcing")
        - Location IDs and prefix define the unique polygons (ie, "usgsbasin-15516000")
        - Read the locations from the warehouse locations table filtering by the prefix
        - Assume polygons are in EPSG:4326 and reproject to the grid's CRS
        - Read a single timestep of the grid from the Icechunk repo
        - Use exactextract to calculate the pixel coverage weights for each polygon
        - Write the pixel coverage weights to the iceberg warehouse table with the domain name and location IDs as keys.
            - Schema: fraction_covered, row, col, location_id, position_index, configuration_name, variable_name, domain_name
        
The second flow will use the pixel coverage weights to calculate mean areal scalar timeseries values
for a given raster layer and polygon layer and write them to the iceberg warehouse table.
    - Inputs
        - Grid layer (raster): Read/loop over all timesteps from an Icechunk repo.
        - Weights: Read from the iceberg warehouse table.
    - Outputs
        - Mean areal values: Write to the iceberg warehouse table as scalar timeseries
    - Approach
        - Read the pixel coverage weights from the iceberg warehouse table with the domain name and location IDs as keys.
        - Read all timesteps of the grid from the Icechunk repo        
        - Calculate mean areal values for each polygon at each timestep using python
        - Write the mean areal values to the iceberg warehouse primary or secondary timeseries table
"""
from typing import Tuple

from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
import icechunk as ic
from exactextract import exact_extract
import geopandas as gpd
import xarray as xr
import rioxarray  # noqa: F401
import pandas as pd
from teehr import Evaluation
from shapely.geometry import box

from workflows.utils.common_utils import initialize_evaluation
from models.mean_areal_inputs import PixelCoverageWeightsInput


@task(timeout_seconds=60 * 2)
def get_readonly_repo_store(
    dest_bucket: str,
    base_prefix: str,
    configuration_name: str,
    s3_storage_kwargs: dict
) -> ic.IcechunkStore:
    """Get a read-only IceChunk S3 repository store for reading the grid data."""
    logger = get_run_logger()
    storage = ic.s3_storage(
        bucket=dest_bucket,
        prefix=f"{base_prefix}/{configuration_name}",
        **s3_storage_kwargs
    )
    repo = ic.Repository.open(storage)
    session = repo.readonly_session(branch="main")
    store = session.store
    logger.info(
        f"IceChunk S3 session store configured at: {dest_bucket}/{base_prefix}/{configuration_name}."
    )
    return store


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 60)
def write_dataframe_to_warehouse(
    ev: Evaluation,
    dataframe: pd.DataFrame,
    table_name: str,
    write_mode: str = "append",
    uniqueness_fields: list[str] = None
):
    """Write the pixel coverage weights to the iceberg warehouse table."""
    logger = get_run_logger()
    logger.info(f"Writing coverage weights to the '{table_name}' warehouse table.")
    ev._write.to_warehouse(
        source_data=dataframe,
        table_name=table_name,
        write_mode=write_mode,
        uniqueness_fields=uniqueness_fields
    )
    logger.info(f"Pixel coverage weights written to the '{table_name}' warehouse table.")


@task(timeout_seconds=60 * 5)
def format_weights_df(
    weights_df: pd.DataFrame,
    grid_width: int,
    configuration_name: str,
    variable_name: str,
    domain_name: str
) -> pd.DataFrame:
    """Format the weights dataframe to match the teehr iceberg warehouse table schema."""
    logger = get_run_logger()
    weights_df = weights_df.explode(["cell_id", "coverage"])
    logger.info("Exploded the weights dataframe.")
    weights_df = weights_df.dropna(subset=["cell_id", "coverage"])
    logger.info("Dropped rows with NaN values in 'cell_id' or 'coverage' columns.")
    weights_df.rename(
        columns={
            "coverage": "fraction_covered",
            "cell_id": "position_index"
        }, inplace=True
    )
    weights_df["row"] = weights_df["position_index"] // grid_width
    weights_df["col"] = weights_df["position_index"] % grid_width
    weights_df["configuration_name"] = configuration_name
    weights_df["variable_name"] = variable_name
    weights_df["domain_name"] = domain_name
    weights_df["row"] = weights_df["row"].astype(int)
    weights_df["col"] = weights_df["col"].astype(int)
    weights_df["position_index"] = weights_df["position_index"].astype(int)
    weights_df["fraction_covered"] = weights_df["fraction_covered"].astype("float32")
    logger.info("Formatted the weights dataframe to match the iceberg warehouse table schema.")
    return weights_df


@task(timeout_seconds=60 * 15)
def run_exact_extract(
    grid_template_da: xr.DataArray,
    polygons_gdf: gpd.GeoDataFrame,
    ops: list = ["cell_id", "coverage"],
    include_cols: list = ["location_id"],
    output: str = "pandas"
) -> pd.DataFrame:
    """Run exactextract to calculate pixel coverage weights for each polygon."""
    logger = get_run_logger()
    logger.info("Running exactextract to calculate pixel coverage weights for each polygon.")
    weights_df = exact_extract(
        rast=grid_template_da,
        vec=polygons_gdf,
        ops=ops,
        include_cols=include_cols,
        output=output
    )
    logger.info("Pixel coverage weights calculated.")
    return weights_df


@task(timeout_seconds=60 * 5)
def check_layer_extents(
    polygons_gdf: gpd.GeoDataFrame,
    grid_da: xr.DataArray
) -> Tuple[gpd.GeoDataFrame, xr.DataArray]:
    """Check the extents of the polygons and grid to ensure they overlap.
    
    If there are polygons outside the grid extent, drop them from the polygons_gdf.
    If the grid extent is larger than the polygon extent, clip the grid layer to the polygon extent.
    """
    logger = get_run_logger()
    logger.info("Checking the extents of the polygons and grid to ensure they overlap.")
    poly_box = box(*polygons_gdf.total_bounds)
    grid_box = box(*grid_da.rio.bounds())
    if not poly_box.intersects(grid_box):
        logger.error("The polygons and grid do not intersect. Please check the input data.")
        raise ValueError("The polygons and grid do not intersect. Please check the input data.")
    if poly_box.contains(grid_box):
        initial_count = len(polygons_gdf)
        polygons_gdf = polygons_gdf[polygons_gdf.within(grid_box)]
        dropped_count = initial_count - len(polygons_gdf)
        if dropped_count > 0:
            logger.info(
                f"Dropped {dropped_count} polygons that are outside the grid extent."
            )
    elif grid_box.contains(poly_box):
        logger.info(
            "The grid layer extends beyond the polygon extent. "
            "Clipping the grid layer to the polygon extent."
        )
        grid_da = grid_da.rio.clip_box(*poly_box.bounds)
    return polygons_gdf, grid_da


@flow(
    name="calculate-pixel-coverage-weights",
    description="Calculate pixel coverage weights for a given grid and polygon layer using exactextract."
)
def calculate_pixel_coverage_weights(args: PixelCoverageWeightsInput):
    """Calculate pixel coverage weights for a given grid and polygon layer using exactextract.

    Parameters
    ----------
    args : PixelCoverageWeightsInput
        Pydantic model containing all flow parameters. See PixelCoverageWeightsInput for field descriptions.
    """
    logger = get_run_logger()

    ev = initialize_evaluation(
        temp_dir_path=args.temp_dir_path,
        start_spark_cluster=args.start_spark_cluster,
    )
    # Read the polygon locations based on the location ID prefix
    polygons_gdf = ev.locations.filter(
        filters=[
            {
                "column": "id",
                "operator": "like",
                "value": f"{args.location_id_prefix}-%"
            }
        ]
    ).to_geopandas()
    polygons_gdf["location_id"] = polygons_gdf["id"].values  # the 'id' column is ignored by exactextract

    # Connect to the IceChunk S3 repository with a read-only session to read the grid data
    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )
    grid_template_da = xr.open_zarr(
        store,
        group="raw_data",
        decode_coords="all"
    )[args.grid_variable_name].isel({args.append_dim: 0}).squeeze(drop=True)
    # TODO: # Ensure latitude and longitude are strictly increasing (left to right/top to bottom)?
    logger.info(f"Grid data read for first {args.append_dim} occurrence. Dimensions of length 1 have been dropped.")

    # Reproject the polygons to the grid's CRS and check extents to ensure they overlap
    polygons_gdf = polygons_gdf.to_crs(grid_template_da.rio.crs)
    polygons_gdf, grid_template_da = check_layer_extents(
        polygons_gdf=polygons_gdf,
        grid_da=grid_template_da
    )

    # Load into memory for exactextract
    grid_template_da = grid_template_da.load()

    # Calculate pixel coverage weights for each polygon using exactextract
    weights_df = run_exact_extract(
        grid_template_da=grid_template_da,
        polygons_gdf=polygons_gdf
    )

    teehr_variable_name = args.variable_and_unit_mapper.variable_name[args.grid_variable_name].name
    weights_df = format_weights_df(
        weights_df=weights_df,
        grid_width=grid_template_da.rio.width,
        configuration_name=args.configuration_name,
        variable_name=teehr_variable_name,
        domain_name=args.domain_name
    )

    # Write the pixel coverage weights to the iceberg warehouse table
    write_dataframe_to_warehouse(
        ev=ev,
        dataframe=weights_df,
        table_name="grid_pixel_coverage_weights",
        uniqueness_fields=["location_id", "domain_name"]
    )