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

from utils.common_utils import initialize_evaluation


logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1

BUCKET_NAME = 'ciroh-community-ngen-datastream'
# VERSION = "v2.2"
YRMODAY = "20251116"
# FORECAST_CONFIG = "short_range"
SHORT_RANGE_REF_TIMES = [f"{ref_time:02d}" for ref_time in range(0, 24)]

# Set up access for public S3 bucket
s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))
# session = botocore.session.Session()

@flow(
    flow_run_name="ingest-datastream-forecasts",
    timeout_seconds=60 * 60,
    retries=2
)
def ingest_datastream_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    datastream_configuration: str = "short_range",
    datastream_version: str = "v2.2"
) -> None:
    """DataStream Forecasts Ingestion.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing DataStream forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    ev = initialize_evaluation(dir_path=dir_path)

    # Construct directory path
    # ex. "ngen.20250812/short_range/{01 - 23}/{VPU}/{troute_file}"

    for ref_time in SHORT_RANGE_REF_TIMES:

        prefix = f"{datastream_version}/ngen.{YRMODAY}/{datastream_configuration}/{ref_time}/"
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=prefix,
            Delimiter='/',
            MaxKeys=100
        )
        # Get list of VPU prefixes
        vpu_prefixes = response.get('CommonPrefixes', [])
        for vpu_prefix in vpu_prefixes:

            # Assemble filepath
            filepath = f"{datastream_version}/ngen.{YRMODAY}/{datastream_configuration}/{ref_time}/{vpu_prefix["Prefix"]}{filename}"

            logger.info(f"Processing file: s3://{BUCKET_NAME}/{filepath}")

            try:
                # Read dataframe from s3 with pyspark
                sdf = ev.spark.read.parquet(filepath)
            except Exception as e:
                logger.error(f"Error reading file {filepath}: {e}")
                continue

            if sdf.isEmpty():
                logger.warning(f"No data found in file: s3://{BUCKET_NAME}/{filepath}")
                continue

            # Load to warehouse. Write to a separate namespace?
            ev.load.dataframe(
                df=sdf,
                table_name="secondary_timeseries"
            )
            logger.info(f"Successfully loaded data from file: s3://{BUCKET_NAME}/{filepath}")

            break

        break

    pass


if __name__ == "__main__":
    ingest_datastream_forecasts(dir_path="/mnt/c/data/ciroh/teehr/datastream/")