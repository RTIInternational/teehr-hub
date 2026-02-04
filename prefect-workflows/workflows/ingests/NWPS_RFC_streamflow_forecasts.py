from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger
from prefect.futures import wait
import pandas as pd

from workflows.utils.common_utils import initialize_evaluation
from utils.datastream_utils import (
    coalesce_cache_files,
    load_to_warehouse
)
from utils.NWPS_RFC_utils import (
    generate_NWPS_endpoints,
    fetch_NWPS_RFC_fcst_to_cache
)
from teehr.utils.utils import remove_dir_if_exists


logging.getLogger("teehr").setLevel(logging.INFO)

CURRENT_DT = datetime.now(UTC)
LOOKBACK_DAYS = 1

LOCATION_ID_PREFIX = "nwpsrfc"

ROOT_NWPS_URL = 'https://api.water.noaa.gov'

FIELD_MAPPING = {
    "validTime": "value_time",
    "secondary": "value",
}
LOCATION_ID_PREFIX = "nwpsrfc"
VARIABLE_NAMES = ["streamflow_hourly_inst",
                  "streamflow_6hr_inst"]
CONFIGURATION_NAME = "nwpsrfc_streamflow_forecast"
UNITS_MAPPING = {
    "streamflow_hourly_inst": "m^3/s",
    "streamflow_6hr_inst": "m^3/s"
}


@flow(
    flow_run_name="ingest-nwps-rfc-forecasts",
    timeout_seconds=60 * 60,
    retries=2
)
def ingest_nwps_rfc_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_cache_files: int = 5
) -> None:
    """RFC streamflow forecast ingestion workflow."""
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    logger.info(f"Processing RFC forecasts issued by: {end_dt}")

    ev = initialize_evaluation(dir_path=dir_path)

    # get existing location ids from warehouse
    # > NWPS can only query by USGS/RFC-ID, so we need to map to those
    # > oddly, the nwm segment is mapped in the metadata just not queriable
    primary_id_list = [
        row[0] for row in ev.location_crosswalks.to_sdf().select("primary_location_id").collect()
    ]

    stripped_ids = []
    for prim_id in primary_id_list:
        prefix = prim_id.split("-")[0]
        id_val = prim_id.split("-")[1]
        if prefix == 'usgs' and id_val not in stripped_ids:
            stripped_ids.append(id_val)

    # set up cache directories
    cache_directories = {}
    for variable_name in VARIABLE_NAMES:
        output_cache_dir = Path(
            ev.cache_dir,
            "fetching",
            "nwps_rfc",
            variable_name
        )
        remove_dir_if_exists(output_cache_dir)
        output_cache_dir.mkdir(parents=True, exist_ok=True)
        cache_directories[variable_name] = output_cache_dir

    # assemble API endpoints
    nwps_endpoints = generate_NWPS_endpoints(
        gage_ids=stripped_ids,
        root_url=ROOT_NWPS_URL,
    )

    # fetch data to cache
    for endpoint in nwps_endpoints:
        logger.info(f"Fetching NWPS RFC forecast data for USGS-ID: {endpoint['usgs_id']}")
        fetch_NWPS_RFC_fcst_to_cache(
            endpoint=endpoint,
            output_cache_dirs=cache_directories,
            field_mapping=FIELD_MAPPING,
            units_mapping=UNITS_MAPPING,
            variable_name=VARIABLE_NAMES,
            configuration_name=CONFIGURATION_NAME,
            location_id_prefix=LOCATION_ID_PREFIX
        )

    logger.info("Completed fetching NWPS RFC forecast data to cache.")

    for output_cache_dir in cache_directories.values():
        logger.info(
            f"Adding cached data to evaluation from: {output_cache_dir}"
            )
        # coalesce cache files
        coalesced_cache_dir = output_cache_dir / "coalesced"
        coalesce_cache_files(
            ev=ev,
            num_cache_files=num_cache_files,
            output_cache_dir=output_cache_dir,
            coalesced_cache_dir=coalesced_cache_dir,
        )

        # load output
        load_to_warehouse(
            ev=ev,
            in_path=coalesced_cache_dir,
            table_name="secondary_timeseries"
        )