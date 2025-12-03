from pathlib import Path
from datetime import datetime, timedelta
from typing import Union
import logging

from prefect import flow, get_run_logger
from prefect.futures import wait
import pandas as pd
import botocore.session
from botocore import UNSIGNED
from botocore.config import Config

from workflows.utils.common_utils import initialize_evaluation
from utils.datastream_utils import (
    fetch_troute_output_to_cache,
    generate_s3_filepaths,
    coalesce_cache_files,
    load_to_warehouse
)
from teehr.utils.utils import remove_dir_if_exists


logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1

BUCKET_NAME = 'ciroh-community-ngen-datastream'

SHORT_RANGE_TZ_HOURS = [f"{ref_time:02d}" for ref_time in range(0, 24)]
SHORT_RANGE_MEMBERS = [None]

MEDIUM_RANGE_TZ_HOURS = ["00", "06", "12", "18"]
MEDIUM_RANGE_MEMBERS = ["1"]

FORMAT_PATTERN = "%Y-%m-%d_%H:%M:%S"
UNITS_MAPPING = {"m3 s-1": "m^3/s"}
LOCATION_ID_PREFIX = "nrds22"
VARIABLE_NAME = "streamflow_hourly_inst"

FORECAST_CONFIGURATION = "short_range"
HYDROFABRIC_VERSION = "v2.2_hydrofabric"
DATASTREAM_NAME = "cfe_nom"
FIELD_MAPPING = {
    "time": "value_time",
    "feature_id": "location_id",
    "flow": "value"
}

# Set up access for public S3 bucket
session = botocore.session.get_session()
s3 = session.create_client(
    's3',
    config=Config(signature_version=UNSIGNED)
)


@flow(
    flow_run_name="ingest-datastream-forecasts",
    timeout_seconds=60 * 60,
    retries=2
)
def ingest_datastream_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: int = LOOKBACK_DAYS,
    forecast_configuration: str = FORECAST_CONFIGURATION,
    hydrofabric_version: str = HYDROFABRIC_VERSION,
    datastream_name: str = DATASTREAM_NAME,
    num_cache_files: int = 5,
) -> None:
    """DataStream Forecasts Ingestion.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - We assume the crosswalk table and configuration name has already been
      loaded to the warehouse.
    - Ultimately, this fetching and loading of DataStream forecasts could be
      part of TEEHR.
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    start_dt = end_dt - timedelta(days=num_lookback_days)
    yrmoday = start_dt.strftime("%Y%m%d")
    logger.info(f"Processing DataStream forecasts for date: {yrmoday}")

    ev = initialize_evaluation(dir_path=dir_path)

    # Get existing location IDs from warehouse
    secondary_id_list = [
        row[0] for row in ev.location_crosswalks.to_sdf().select("secondary_location_id").collect()
    ]
    stripped_ids = []
    for sec_id in secondary_id_list:
        prefix = sec_id.split("-")[0]
        id_val = sec_id.split("-")[1]
        if prefix == "nrds22":
            stripped_ids.append(id_val)

    # Get tz hours and members based on forecast configuration
    if forecast_configuration == "short_range":
        ref_tz_hours = SHORT_RANGE_TZ_HOURS
        members = SHORT_RANGE_MEMBERS
    elif forecast_configuration == "medium_range":
        ref_tz_hours = MEDIUM_RANGE_TZ_HOURS
        members = MEDIUM_RANGE_MEMBERS
    else:
        logger.error(
            f"Invalid forecast configuration: {forecast_configuration}. "
            "Must be 'short_range' or 'medium_range'."
        )
        return

    configuration_name = f"nrds_v22_{datastream_name.replace("_", "")}_{forecast_configuration}"

    # Set up cache directory
    output_cache_dir = Path(
        ev.cache_dir,
        "fetching",
        "nrds",
        configuration_name,
        VARIABLE_NAME
    )
    remove_dir_if_exists(output_cache_dir)
    output_cache_dir.mkdir(parents=True, exist_ok=True)

    s3_filepaths = generate_s3_filepaths(
        forecast_configuration=forecast_configuration,
        hydrofabric_version=hydrofabric_version,
        datastream_name=datastream_name,
        yrmoday=yrmoday,
        start_dt=start_dt,
        members=members,
        ref_tz_hours=ref_tz_hours,
        bucket_name=BUCKET_NAME,
        s3=s3
    )

    for filepath_info in s3_filepaths:
        logger.info(
            f"Fetching troute output from S3 for {configuration_name}: {filepath_info['filepath']}"
        )
        # Fetch troute output to cache
        fetch_troute_output_to_cache(
            filepath_info=filepath_info,
            output_cache_dir=output_cache_dir,
            bucket_name=BUCKET_NAME,
            warehouse_ngen_ids=stripped_ids,
            field_mapping=FIELD_MAPPING,
            units_mapping=UNITS_MAPPING,
            variable_name=VARIABLE_NAME,
            configuration_name=configuration_name,
            location_id_prefix=LOCATION_ID_PREFIX,
        )

    # futures = []
    # for filepath_info in s3_filepaths:
    #     logger.info(
    #         f"Fetching troute output from S3 for {configuration_name}: {filepath_info['filepath']}"
    #     )
    #     # Fetch troute output to cache
    #     future = fetch_troute_output_to_cache.submit(
    #         filepath_info=filepath_info,
    #         output_cache_dir=output_cache_dir,
    #         bucket_name=BUCKET_NAME,
    #         warehouse_ngen_ids=stripped_ids,
    #         field_mapping=FIELD_MAPPING,
    #         units_mapping=UNITS_MAPPING,
    #         variable_name=VARIABLE_NAME,
    #         configuration_name=configuration_name,
    #         location_id_prefix=LOCATION_ID_PREFIX,
    #     )
    #     futures.append(future)
    # wait(futures)

    # Coalesce cache files for optimized loading
    coalesced_cache_dir = output_cache_dir / "coalesced"
    coalesce_cache_files(
        ev=ev,
        num_cache_files=num_cache_files,
        output_cache_dir=output_cache_dir,
        coalesced_cache_dir=coalesced_cache_dir
    )

    # Load output
    load_to_warehouse(
        ev=ev,
        in_path=coalesced_cache_dir,
        table_name="secondary_timeseries"
    )
