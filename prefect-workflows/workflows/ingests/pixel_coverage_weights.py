"""Calculate pixel coverage weights of location polygons on an Icechunk grid.

Weights are written to the warehouse keyed by location, pixel and grid_name, the grid they
index (CRS, pixel size, extent). They are shared by every variable and configuration on
that grid. A MERGE never deletes, so pixels a re-drawn polygon no longer covers stay
in the table.
"""
import geopandas as gpd
import icechunk as ic
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from shapely.geometry import box
from teehr import Evaluation
from teehr.utilities.generate_weights import generate_weights_file

from utils import grid_utils as gu
from utils import time_grid as tg
from workflows.utils.common_utils import initialize_evaluation, table_exists
from workflows.models.mean_areal_inputs import PixelCoverageWeightsInput

WEIGHTS_TABLE_NAME = "grid_pixel_coverage_weights"
WEIGHTS_UNIQUENESS_FIELDS = ["location_id", "row", "col", "grid_name"]
WEIGHTS_PARTITION_BY = ["grid_name"]
# Equal-area CRS for comparing polygon areas
EQUAL_AREA_CRS = "EPSG:6933"
# Spark settings for the weights and mean areal flows: Arrow converts pandas <-> Spark ~10x faster (weights,
# timeseries writes), and a failed conversion errors instead of silently taking the slow path
ARROW_CONFIGS = {
    "spark.sql.execution.arrow.pyspark.enabled": "true",
    "spark.sql.execution.arrow.pyspark.fallback.enabled": "false",
}


@task(timeout_seconds=60 * 2)
def get_readonly_repo_store(
    dest_bucket: str,
    base_prefix: str,
    configuration_name: str,
    s3_storage_kwargs: dict
) -> ic.IcechunkStore:
    """Get a read-only IceChunk S3 repository store for reading the grid data from its data group."""
    logger = get_run_logger()
    storage = gu.build_icechunk_s3_storage(
        bucket=dest_bucket,
        prefix=f"{base_prefix}/{configuration_name}",
        **s3_storage_kwargs
    )
    # The data group may be /references, read from the source
    repo = gu.open_repo_for_reading(storage)
    session = repo.readonly_session(branch="main")
    store = session.store
    logger.info(
        f"IceChunk S3 session store configured at: {dest_bucket}/{base_prefix}/{configuration_name}."
    )
    return store


@task(cache_policy=NO_CACHE)
def resolve_grid_name(store: ic.IcechunkStore, grid_name: str | None, configuration_name: str) -> str:
    """The grid_name arg, else the repo's grid_name attribute, else the configuration name."""
    logger = get_run_logger()
    stored = tg.read_grid_name(store)
    if grid_name is not None and stored is not None and grid_name != stored:
        # Weights of another grid would index the wrong pixels
        raise ValueError(f"grid_name '{grid_name}' differs from the repo's grid_name attribute '{stored}'.")
    if grid_name is not None:
        logger.info(f"Using grid_name '{grid_name}' from the flow args.")
        return grid_name
    if stored is not None:
        logger.info(f"Using grid_name '{stored}' from the repo.")
        return stored
    logger.info(f"The repo has no grid_name; using the configuration name '{configuration_name}'.")
    return configuration_name


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 60)
def write_dataframe_to_warehouse(
    ev: Evaluation,
    dataframe: pd.DataFrame,
    table_name: str,
    write_mode: str = "append",
    uniqueness_fields: list[str] = None,
    catalog_name: str = None,
    namespace_name: str = None,
    partition_by: list[str] = None,
    replace_condition: str = None,
):
    """Write a pandas or Spark dataframe to an iceberg warehouse table."""
    logger = get_run_logger()
    rows = f"{len(dataframe)} rows" if isinstance(dataframe, pd.DataFrame) else "rows"
    logger.info(f"Writing {rows} to the '{table_name}' warehouse table with write_mode='{write_mode}'.")
    ev._write.to_warehouse(
        source_data=dataframe,
        table_name=table_name,
        write_mode=write_mode,
        uniqueness_fields=uniqueness_fields,
        catalog_name=catalog_name,
        namespace_name=namespace_name,
        partition_by=partition_by,
        replace_condition=replace_condition,
    )
    logger.info(f"Rows written to the '{table_name}' warehouse table.")


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 5)
def format_weights_df(
    weights_df: pd.DataFrame,
    configuration_name: str,
    grid_name: str
) -> pd.DataFrame:
    """Format teehr's weights to the warehouse table schema.

    ``row``/``col`` index the full stored grid named ``grid_name``.
    """
    logger = get_run_logger()
    if weights_df.empty:
        raise ValueError("No grid pixels intersect the polygons.")
    weights_df = weights_df.rename(columns={"weight": "fraction_covered"})
    duplicated = weights_df.duplicated(subset=["location_id", "row", "col"])
    if duplicated.any():
        raise ValueError(
            f"{duplicated.sum()} duplicate (location_id, row, col) weights, e.g. "
            f"{weights_df.loc[duplicated, 'location_id'].unique()[:5].tolist()}. Check for duplicate location ids."
        )
    weights_df["configuration_name"] = configuration_name
    weights_df["grid_name"] = grid_name
    weights_df["row"] = weights_df["row"].astype(int)
    weights_df["col"] = weights_df["col"].astype(int)
    weights_df["fraction_covered"] = weights_df["fraction_covered"].astype("float32")
    logger.info(f"Formatted {len(weights_df)} weight rows.")
    return weights_df


@task(timeout_seconds=60 * 5)
def filter_polygons_by_coverage(
    polygons_gdf: gpd.GeoDataFrame,
    grid_da: xr.DataArray,
    min_coverage: float
) -> gpd.GeoDataFrame:
    """Keep polygons with at least ``min_coverage`` of their area inside the grid extent."""
    logger = get_run_logger()
    grid_box = box(*grid_da.rio.bounds())
    inside = polygons_gdf.geometry.intersection(grid_box)
    fraction = inside.to_crs(EQUAL_AREA_CRS).area / polygons_gdf.geometry.to_crs(EQUAL_AREA_CRS).area
    kept = polygons_gdf[(fraction >= min_coverage).to_numpy()]
    logger.info(
        f"Kept {len(kept)} of {len(polygons_gdf)} polygons with at least {min_coverage:.0%} of their area in the grid."
    )
    if kept.empty:
        raise ValueError(f"No polygons have at least {min_coverage:.0%} of their area inside the grid.")
    return kept


@task(cache_policy=NO_CACHE, timeout_seconds=60 * 10)
def read_location_polygons(ev: Evaluation, location_id_prefix: str) -> gpd.GeoDataFrame:
    """The polygon locations whose ids start with ``location_id_prefix``."""
    polygons_gdf = ev.locations.filter(
        filters=[{"column": "id", "operator": "like", "value": like_prefix(location_id_prefix)}]
    ).to_geopandas()
    if polygons_gdf.empty:
        raise ValueError(f"No locations found with prefix '{location_id_prefix}'.")
    return polygons_gdf


def like_prefix(location_id_prefix: str) -> str:
    """A LIKE pattern for ids starting with ``<prefix>-``, with the prefix's own wildcards escaped.

    Keeps reads to exactly the ids a write's ``startswith`` replace condition covers.
    """
    escaped = location_id_prefix.replace("_", "\\_").replace("%", "\\%")
    return f"{escaped}-%"


def weights_for_grid(
    polygons_gdf: gpd.GeoDataFrame,
    template_da: xr.DataArray,
    x_dim: str,
    y_dim: str,
    min_coverage: float,
    configuration_name: str,
    grid_name: str,
) -> pd.DataFrame:
    """Pixel coverage weights of the polygons on a grid, formatted for the warehouse table.

    ``template_da`` is any variable of the grid, opened lazily; only its geometry is used.
    """
    logger = get_run_logger()
    missing_dims = {x_dim, y_dim} - set(template_da.dims)
    if missing_dims:
        raise ValueError(
            f"Grid has no dimension(s) {sorted(missing_dims)}; set x_dim/y_dim. Dims: {template_da.dims}"
        )
    # teehr requires x/y dims; positions are unchanged, so row/col still index the stored grid.
    # teehr uses only the grid geometry, so the data isn't read.
    template_da = template_da.rename({x_dim: "x", y_dim: "y"})
    polygons_gdf = polygons_gdf.to_crs(template_da.rio.crs)
    # Some source polygons are invalid (degenerate or self-intersecting segments); repair as teehr does.
    polygons_gdf.geometry = polygons_gdf.geometry.make_valid(method="structure", keep_collapsed=False)
    polygons_gdf = filter_polygons_by_coverage(
        polygons_gdf=polygons_gdf,
        grid_da=template_da,
        min_coverage=min_coverage
    )
    # Shared with standalone teehr: one implementation, one row/col convention.
    weights_df = generate_weights_file(
        zone_polygons=polygons_gdf,
        template_dataset=template_da.to_dataset(name="template"),
        variable_name="template",
        output_weights_filepath=None,
        crs_wkt=template_da.rio.crs.to_wkt(),
        unique_zone_id="id",
    )
    logger.info(f"Generated weights for {weights_df['location_id'].nunique()} location(s).")
    return format_weights_df(weights_df=weights_df, configuration_name=configuration_name, grid_name=grid_name)


def write_weights(ev: Evaluation, weights_df: pd.DataFrame, write_mode: str):
    """Write formatted weights, creating the table on first use."""
    write_dataframe_to_warehouse(
        ev=ev,
        dataframe=weights_df,
        table_name=WEIGHTS_TABLE_NAME,
        uniqueness_fields=WEIGHTS_UNIQUENESS_FIELDS,
        write_mode=write_mode if table_exists(ev=ev, table_name=WEIGHTS_TABLE_NAME) else "create_or_replace",
        partition_by=WEIGHTS_PARTITION_BY,
    )


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
        update_configs=ARROW_CONFIGS,
    )
    polygons_gdf = read_location_polygons(ev, args.location_id_prefix)

    store = get_readonly_repo_store(
        dest_bucket=args.dest_bucket,
        base_prefix=args.base_prefix,
        configuration_name=args.configuration_name,
        s3_storage_kwargs=args.s3_storage_kwargs
    )
    grid_name = resolve_grid_name(store, args.grid_name, args.configuration_name)
    grid_ds = xr.open_zarr(store, group=gu.read_data_group(store), decode_coords="all", chunks=None)
    variable_name = args.grid_variable_name or next(iter(grid_ds.data_vars))
    logger.info(f"Using the '{variable_name}' grid as the template.")

    weights_df = weights_for_grid(
        polygons_gdf=polygons_gdf,
        template_da=grid_ds[variable_name],
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        min_coverage=args.min_valid_coverage,
        configuration_name=args.configuration_name,
        grid_name=grid_name,
    )
    write_weights(ev, weights_df, args.write_mode)
