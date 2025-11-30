from pathlib import Path
from datetime import datetime, timedelta
from typing import Union
import logging

from prefect import flow, get_run_logger
import pandas as pd
import botocore.session
from botocore import UNSIGNED
from botocore.config import Config

from utils.common_utils import initialize_evaluation
from utils.datastream_utils import fetch_troute_output_as_dataframe


logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1

BUCKET_NAME = 'ciroh-community-ngen-datastream'
SHORT_RANGE_TZ_HOURS = [f"{ref_time:02d}" for ref_time in range(0, 24)]
FORMAT_PATTERN = "%Y-%m-%d_%H:%M:%S"
UNITS_MAPPING = {"m3 s-1": "m^3/s"}
LOCATION_ID_PREFIX = "nrds22"
VARIABLE_NAME = "streamflow_hourly_inst"
CONFIGURATION_NAME = "nrds_v22_cfenom_short_range"
FORECAST_CONFIGURATION = "short_range"
HYDROFABRIC_VERSION = "v2.2"
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
    hydrofabric_version: str = HYDROFABRIC_VERSION
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

    storage_options = {'anon': True}  # For xarray s3 access
    for ref_tz_hour in SHORT_RANGE_TZ_HOURS:

        prefix = f"{hydrofabric_version}/ngen.{yrmoday}/{forecast_configuration}/{ref_tz_hour}/"
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/',
            MaxKeys=100
        )

        # The troute filename currently uses the first valid time
        file_valid_time = f"{int(ref_tz_hour) + 1:02d}"
        # Construct reference time from s3 path
        ref_time = datetime.strptime(f"{yrmoday}{ref_tz_hour}", "%Y%m%d%H")

        # Get list of VPU prefixes
        vpu_prefixes = response.get('CommonPrefixes', [])
        for vpu_prefix in vpu_prefixes:

            filename = f"troute_output_{yrmoday}{file_valid_time}00.nc"
            # Note. The vpu_prefix['Prefix'] includes the trailing slash
            filepath = f"{vpu_prefix['Prefix']}ngen-run/outputs/troute/{filename}"

            logger.info(f"Processing file: s3://{BUCKET_NAME}/{filepath}")
            df = fetch_troute_output_as_dataframe(
                s3_filepath=f"s3://{BUCKET_NAME}/{filepath}",
                storage_options=storage_options,
                warehouse_ngen_ids=stripped_ids,
                field_mapping=FIELD_MAPPING,
                units_mapping=UNITS_MAPPING,
                variable_name=VARIABLE_NAME,
                configuration_name=CONFIGURATION_NAME,
                ref_time=ref_time,
            )
            if df is None:
                logger.warning(
                    f"Skipping file due to read error or no data: "
                    f"s3://{BUCKET_NAME}/{filepath}"
                )
                continue

            logger.info(
                f"Loading {len(df)} records to warehouse from file: "
                f"s3://{BUCKET_NAME}/{filepath}"
            )
            # Load to warehouse
            ev.load.dataframe(
                df=df,
                table_name="secondary_timeseries"
            )
            logger.info(
                "Successfully loaded data from file: "
                f"s3://{BUCKET_NAME}/{filepath}"
            )
