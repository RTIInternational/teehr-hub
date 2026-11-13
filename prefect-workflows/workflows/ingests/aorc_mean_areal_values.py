"""Mean areal values of AORC v1.1 1 km forcing, read in place from NOAA's yearly Zarr stores.

Each year is its own store (``s3://noaa-nws-aorc-v1-1-1km/<YYYY>.zarr``, chunks of 144 hours), so the flow
reads one year at a time with the shared mean areal core; batches follow the stores' chunks.
"""
import numpy as np
import obstore
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from obstore.store import S3Store
from prefect import flow, get_run_logger
from zarr.storage import ObjectStore

from utils.grid_spec import GridSpec
from workflows.models.external_grid_inputs import AORCMeanArealInput
from workflows.utils.time_utils import to_naive_utc
from mean_areal_values import mean_areal_evaluation, mean_areal_for_grid, prepare_mean_areal
from pixel_coverage_weights import read_location_polygons, weights_for_grid, write_weights

AORC_BUCKET = "noaa-nws-aorc-v1-1-1km"
AORC_REGION = "us-east-1"
AORC_CRS = "EPSG:4326"
FIRST_YEAR = 1979
# Source variable -> teehr variable, unit and scale from the source units, used unless the flow args set them
TEEHR_VARIABLES = {
    # kg/m^2 per hour -> mm/s
    "APCP_surface": ("rainrate_hourly_mean", "mm/s", 1 / 3600),
}


def _year_store(year: int) -> S3Store:
    return S3Store(AORC_BUCKET, prefix=f"{year}.zarr", region=AORC_REGION, skip_signature=True)


def open_aorc_year(year: int, variable: str) -> xr.DataArray:
    """One year of an AORC variable, lazily opened and CF-decoded to float32, with its CRS."""
    ds = xr.open_zarr(
        ObjectStore(_year_store(year), read_only=True), zarr_format=2, consolidated=True, chunks=None,
        decode_cf=False,
    )[[variable]]
    # The packing attrs come as Python floats, which would decode the int16 values to float64
    for name in ("scale_factor", "add_offset"):
        if name in ds[variable].attrs:
            ds[variable].attrs[name] = np.float32(ds[variable].attrs[name])
    return (
        xr.decode_cf(ds)[variable]
        .rio.write_crs(AORC_CRS)
        .rio.set_spatial_dims(x_dim="longitude", y_dim="latitude")
    )


def available_years(start_year: int, end_year: int) -> list[int]:
    """Years in start..end with a store, logging each store's last change so source rewrites can be traced."""
    logger = get_run_logger()
    years = []
    for year in range(max(start_year, FIRST_YEAR), end_year + 1):
        try:
            meta = obstore.head(_year_store(year), ".zmetadata")
        except FileNotFoundError:
            logger.info(f"No AORC store for {year}.")
            continue
        logger.info(f"AORC {year}: .zmetadata last modified {meta['last_modified']}.")
        years.append(year)
    return years


def with_teehr_names(args: AORCMeanArealInput) -> AORCMeanArealInput:
    """The args with the variable's teehr name, unit and scale from TEEHR_VARIABLES, unless variable_name is set.

    Goes by values, not by which fields were passed: Prefect's run form sends every field, defaults included.
    """
    if args.variable_name is not None:
        if args.unit_name is None:
            raise ValueError("Set unit_name (and value_scale) with variable_name.")
        return args
    if args.unit_name is not None:
        raise ValueError("Set variable_name (and value_scale) with unit_name.")
    known = TEEHR_VARIABLES.get(args.grid_variable_name)
    if known is None:
        raise ValueError(f"Set variable_name, unit_name and value_scale for AORC variable '{args.grid_variable_name}'.")
    variable_name, unit_name, scale = known
    return args.model_copy(update={"variable_name": variable_name, "unit_name": unit_name, "value_scale": scale})


@flow(
    name="calculate-aorc-mean-areal-values",
    description="Calculate mean areal values of AORC v1.1 1 km forcing for a polygon layer from NOAA's Zarr stores."
)
def calculate_aorc_mean_areal_values(args: AORCMeanArealInput):
    """Calculate mean areal values of an AORC variable over start_dt..end_dt, one year at a time."""
    logger = get_run_logger()
    args = with_teehr_names(args)
    start = to_naive_utc(args.start_dt) if args.start_dt is not None else pd.Timestamp(f"{FIRST_YEAR}-01-01")
    end = to_naive_utc(args.end_dt) if args.end_dt is not None else pd.Timestamp.now()
    years = available_years(start.year, end.year)
    if not years:
        logger.info("No AORC years in the requested window.")
        return

    ev = mean_areal_evaluation(args)
    spec = GridSpec(append_dim="time", grid_name=args.grid_name)
    target = prepare_mean_areal(ev, open_aorc_year(years[0], args.grid_variable_name), args, args.grid_name)
    for year in years:
        logger.info(f"Computing AORC {year}.")
        mean_areal_for_grid(ev, open_aorc_year(year, args.grid_variable_name), spec, args, target)
    logger.info("AORC mean areal values completed.")


@flow(
    name="calculate-aorc-pixel-coverage-weights",
    description="Calculate pixel coverage weights of a polygon layer on the AORC v1.1 1 km grid."
)
def calculate_aorc_pixel_coverage_weights(args: AORCMeanArealInput):
    """Calculate the polygons' pixel coverage weights on the AORC grid (one year's store as the template)."""
    ev = mean_areal_evaluation(args)
    weights_df = weights_for_grid(
        polygons_gdf=read_location_polygons(ev, args.location_id_prefix),
        template_da=open_aorc_year(args.template_year, args.grid_variable_name),
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        min_coverage=args.min_valid_coverage,
        configuration_name=args.configuration_name,
        grid_name=args.grid_name,
    )
    write_weights(ev, weights_df, args.write_mode, args.location_id_prefix, args.grid_name)
