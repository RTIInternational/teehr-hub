"""Mean areal values of a dynamical.org Icechunk collection (e.g. GEFS), read in place.

The repo is found through its STAC record, as dynamical asks (hrefs move between versions), and opened
anonymously. Its layout is stated by the deployment (append dim, fixed dims, renames), not inferred.
"""
import httpx
import icechunk as ic
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from prefect import flow, get_run_logger, task

from utils import grid_utils as gu
from utils.grid_spec import GridSpec, open_grid_dataset, read_grid_spec
from workflows.models.external_grid_inputs import DynamicalMeanArealInput
from workflows.utils import repo_const as rc
from mean_areal_values import mean_areal_evaluation, mean_areal_for_grid, prepare_mean_areal
from pixel_coverage_weights import read_location_polygons, weights_for_grid, write_weights


@task(retries=2, retry_delay_seconds=10)
def resolve_stac_icechunk(stac_collection_url: str, asset: str) -> tuple[str, str]:
    """The bucket and prefix of a STAC collection's Icechunk asset."""
    response = httpx.get(stac_collection_url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    collection = response.json()
    href = collection["assets"][asset]["href"]
    if not href.startswith("s3://"):
        raise ValueError(f"Asset '{asset}' of {stac_collection_url} isn't an s3:// href: {href}")
    bucket, _, prefix = href.removeprefix("s3://").partition("/")
    get_run_logger().info(
        f"Reading {href} (license {collection.get('license', 'unknown')})."
    )
    return bucket, prefix.rstrip("/")


def open_dynamical_grid(args: DynamicalMeanArealInput) -> tuple[xr.DataArray, GridSpec]:
    """The collection's variable, lazily opened with canonical dims, and its grid spec."""
    logger = get_run_logger()
    bucket, prefix = resolve_stac_icechunk(args.stac_collection_url, args.asset)
    storage = ic.s3_storage(
        bucket=bucket, prefix=prefix, region=args.region, anonymous=True, endpoint_url=args.endpoint_url
    )
    # Virtual collections reference public source buckets; their containers are authorized anonymously
    session = gu.open_repo_for_reading(storage).readonly_session(branch=args.branch)
    logger.info(f"Opened {bucket}/{prefix} at snapshot {session.snapshot_id}.")
    spec = read_grid_spec(session.store, override={
        rc.APPEND_DIM_ATTR: args.append_dim,
        rc.FIXED_DIMS_ATTR: args.fixed_dims,
        rc.DATA_GROUP_ATTR: "/",
        "renames": args.renames,
    })
    da = open_grid_dataset(session.store, spec)[args.grid_variable_name]
    return da.rio.set_spatial_dims(x_dim=args.x_dim, y_dim=args.y_dim), spec


@flow(
    name="calculate-dynamical-mean-areal-values",
    description="Calculate mean areal values of a dynamical.org Icechunk collection (e.g. GEFS) for a polygon layer."
)
def calculate_dynamical_mean_areal_values(args: DynamicalMeanArealInput):
    """Calculate mean areal values of a dynamical.org collection variable over start_dt..end_dt."""
    if args.start_dt is None and args.num_lookback_days is not None:
        args = args.model_copy(update={
            "start_dt": (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=args.num_lookback_days)).floor("D")
        })
    ev = mean_areal_evaluation(args)
    grid_da, spec = open_dynamical_grid(args)
    target = prepare_mean_areal(ev, grid_da, args, args.grid_name)
    mean_areal_for_grid(ev, grid_da, spec, args, target)
    get_run_logger().info("Dynamical mean areal values completed.")


@flow(
    name="calculate-dynamical-pixel-coverage-weights",
    description="Calculate pixel coverage weights of a polygon layer on a dynamical.org collection's grid."
)
def calculate_dynamical_pixel_coverage_weights(args: DynamicalMeanArealInput):
    """Calculate the polygons' pixel coverage weights on the collection's grid."""
    ev = mean_areal_evaluation(args)
    grid_da, _ = open_dynamical_grid(args)
    weights_df = weights_for_grid(
        polygons_gdf=read_location_polygons(ev, args.location_id_prefix),
        template_da=grid_da,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        min_coverage=args.min_valid_coverage,
        configuration_name=args.configuration_name,
        grid_name=args.grid_name,
    )
    # MERGE: weights of other layers on the grid are kept
    write_weights(ev, weights_df, write_mode="upsert")
