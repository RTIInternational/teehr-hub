from pathlib import Path
from datetime import datetime, timedelta
from typing import Union
import logging

from prefect import flow, get_run_logger
import pandas as pd
import boto3
import botocore
from botocore import UNSIGNED
from botocore.config import Config
import xarray as xr

import teehr
from utils.common_utils import initialize_evaluation


logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1

BUCKET_NAME = 'ciroh-community-ngen-datastream'
# VERSION = "v2.2"
# YRMODAY = "20251116"
# FORECAST_CONFIG = "short_range"
SHORT_RANGE_TZ_HOURS = [f"{ref_time:02d}" for ref_time in range(0, 24)]
FORMAT_PATTERN = "%Y-%m-%d_%H:%M:%S"
UNITS_MAPPING = {"m3 s-1": "m^3/s"}
LOCATION_ID_PREFIX = "nrds22"
CONFIGURATION_NAME = "nrds_v22_cfenom_short_range"
FORECAST_CONFIGURATION = "short_range"
HYDROFABRIC_VERSION = "v2.2"
FIELD_MAPPING = {
    "time": "value_time",
    "feature_id": "location_id",
    "flow": "value"
}

# Set up access for public S3 bucket
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))


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
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    start_dt = end_dt - timedelta(days=num_lookback_days)
    yrmoday = start_dt.strftime("%Y%m%d")
    logger.info(f"Processing DataStream forecasts for date: {yrmoday}")

    ev = initialize_evaluation(dir_path=dir_path)

    # Get existing location IDs from warehouse
    # Todo: Use pyspark here instead?
    locations_df = ev.locations.to_pandas()

    # Note. Assumes crosswalk is already loaded
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

            # # TEMP!
            # if "VPU16" not in vpu_prefix['Prefix']:
            #     continue

            filename = f"troute_output_{yrmoday}{file_valid_time}00.nc"
            # Note. The vpu_prefix['Prefix'] includes the trailing slash
            filepath = f"{hydrofabric_version}/ngen.{yrmoday}/{forecast_configuration}/{ref_tz_hour}/{vpu_prefix['Prefix']}ngen-run/outputs/troute/{filename}"

            logger.info(f"Processing file: s3://{BUCKET_NAME}/{filepath}")
            try:
                # Open the dataset with xarray, specifying the engine
                ds = xr.open_dataset(
                    f"s3://{BUCKET_NAME}/{filepath}", engine="h5netcdf"
                )
                field_list = [field for field in FIELD_MAPPING if field in ds]
                df = ds[field_list].to_dataframe()
                df.reset_index(inplace=True)
                df.rename(columns=FIELD_MAPPING, inplace=True)
                unit_name = UNITS_MAPPING[ds.flow.units]
            except Exception as e:
                logger.error(f"Error reading file {filepath}: {e}")
                continue

            if df.empty:
                logger.warning(
                    f"No data found in file: s3://{BUCKET_NAME}/{filepath}"
                )
                continue

            constant_field_values = {
                "unit_name": unit_name,
                "variable_name": "streamflow_hourly_inst",
                "configuration_name": CONFIGURATION_NAME,
                "reference_time": ref_time
            }
            for key in constant_field_values.keys():
                df[key] = constant_field_values[key]

            logger.info("Limiting to existing location IDs in warehouse")
            # Limit to locations that exist in the warehouse
            df_clip = df[df.primary_location_id.isin(locations_df["id"])]

            logger.info(
                f"Loading {len(df_clip)} records to warehouse from file: "
                f"s3://{BUCKET_NAME}/{filepath}"
            )
            # Load to warehouse. Write to a separate namespace?
            ev.load.dataframe(
                df=df_clip,
                table_name="secondary_timeseries",
                secondary_location_id_prefix=LOCATION_ID_PREFIX
            )
            logger.info(
                "Successfully loaded data from file: "
                f"s3://{BUCKET_NAME}/{filepath}"
            )

    pass


# if __name__ == "__main__":
#     ingest_datastream_forecasts(dir_path="/mnt/c/data/ciroh/teehr/datastream/")