from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger
from prefect.futures import wait
import pandas as pd

from workflows.utils.common_utils import initialize_evaluation
from teehr.utils.utils import remove_dir_if_exists
from teehr.models.fetching.nwm30_point import PointConfigurationModel

from utils.datastream_utils import (
    coalesce_cache_files,
    load_to_warehouse
)
from utils.nwm31se_utils import (
    generate_nwm31se_endpoints,
    fetch_channelrt_output_to_cache
)


logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now(UTC)
LOOKBACK_DAYS = 1

SHORT_RANGE_TZ_HOURS = [f"{ref_time:02d}" for ref_time in range(0, 24)]
SHORT_RANGE_MEMBERS = [None]

MEDIUM_RANGE_TZ_HOURS = ["00", "06", "12", "18"]
MEDIUM_RANGE_MEMBERS = ["1"]

FORMAT_PATTERN = "%Y-%m-%d_%H:%M:%S"
UNITS_MAPPING = {"m3 s-1": "m^3/s"}
LOCATION_ID_PREFIX = "nwm31se"
VARIABLE_NAME = "streamflow_hourly_inst"

FORECAST_CONFIGURATION = "short_range"
FIELD_MAPPING = {
    "time": "value_time",
    "feature_id": "location_id",
    "flow": "value"
}

# define NWM31SE root URL
NWM31SE_ROOT_URL = "https://hydrology.nws.noaa.gov/pub/nwm/v3.1/wcoss-data"


@flow(
    flow_run_name="ingest-nwm31se-forecasts",
    timeout_seconds=60 * 60,
    retries=2
)
def ingest_nwm31se_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    forecast_configuration: str = FORECAST_CONFIGURATION,
    num_cache_files: int = 5,
) -> None:
    """NWM 3.1 SE Streamflow Forecasts Ingestion.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing NWM forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    start_dt = end_dt - timedelta(days=num_lookback_days)
    yrmoday = start_dt.strftime("%Y%m%d")
    logger.info(f"Processing NWM 3.1 SE forecasts for date: {yrmoday}")

    ev = initialize_evaluation(dir_path=dir_path)

    # get existing location IDs from warehouse
    secondary_id_list = [
        row[0] for row in ev.location_crosswalks.to_sdf().select("secondary_location_id").collect()
    ]
    stripped_ids = []
    for sec_id in secondary_id_list:
        prefix = sec_id.split("-")[0]
        id_val = sec_id.split("-")[1]
        if prefix == "nwm31se":
            stripped_ids.append(id_val)

    # get tz hours and members based on forecast configuration
    if forecast_configuration == "short_range":
        tz_hours = SHORT_RANGE_TZ_HOURS
        members = SHORT_RANGE_MEMBERS
    elif forecast_configuration == "medium_range":
        tz_hours = MEDIUM_RANGE_TZ_HOURS
        members = MEDIUM_RANGE_MEMBERS
    else:
        logger.error(
            f"Invalid forecast configuration: {forecast_configuration}. "
            "Must be 'short_range' or 'medium_range'."
        )
        return

    configuration_name = f"nwm31se_{forecast_configuration}"

    # set up cache directory
    output_cache_dir = Path(
        ev.cache_dir,
        "fetching",
        "nwm31se",
        configuration_name,
        VARIABLE_NAME
    )
    remove_dir_if_exists(output_cache_dir)
    output_cache_dir.mkdir(parents=True, exist_ok=True)

    # obtain endpoints to fetch
    endpoints = generate_nwm31se_endpoints(
        root_url=NWM31SE_ROOT_URL,
        yrmoday=yrmoday,
        forecast_configuration=forecast_configuration,
        members=members,
        ref_tz_hours=tz_hours,
        start_dt=start_dt
    )

    # fetch data to cache
    for endpoint_info in endpoints:
        logger.info(
            f"Fetching channel_rt data for {configuration_name}: {endpoint_info['endpoint']}"
        )
        fetch_channelrt_output_to_cache(
            filepath_info=endpoint_info,
            warehouse_ngen_ids=stripped_ids,
            field_mapping=FIELD_MAPPING,
            units_mapping=UNITS_MAPPING,
            variable_name=VARIABLE_NAME,
            configuration_name=configuration_name,
            location_id_prefix=LOCATION_ID_PREFIX,
            output_cache_dir=output_cache_dir,
        )

    # coalesce cache files
    coalesced_cache_dir = Path(output_cache_dir, "coalesced")
    coalesce_cache_files(
        ev=ev,
        num_cache_files=num_cache_files,
        output_cache_dir=output_cache_dir,
        coalesced_cache_dir=coalesced_cache_dir,
    )

    # load to warehouse
    load_to_warehouse(
        ev=ev,
        in_path=coalesced_cache_dir,
        table_name="secondary_timeseries"
    )
