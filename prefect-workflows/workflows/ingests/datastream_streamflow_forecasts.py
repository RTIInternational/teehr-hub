from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger
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
from pyspark.sql import functions as F
from teehr.utils.utils import remove_dir_if_exists


logging.getLogger("teehr").setLevel(logging.INFO)


LOOKBACK_DAYS = 1

BUCKET_NAME = 'ciroh-community-ngen-datastream'

SHORT_RANGE_TZ_HOURS = [f"{ref_time:02d}" for ref_time in range(0, 24)]
SHORT_RANGE_MEMBERS = [None]

MEDIUM_RANGE_TZ_HOURS = ["00", "06", "12", "18"]
MEDIUM_RANGE_MEMBERS = ["1"]

FORMAT_PATTERN = "%Y-%m-%d_%H:%M:%S"
UNIT_NAME = "m^3/s"
LOCATION_ID_PREFIX = "nrds22"
VARIABLE_NAME = "streamflow_hourly_inst"

FORECAST_CONFIGURATION = "short_range"
HYDROFABRIC_VERSION = "v2.2_hydrofabric"
DATASTREAM_NAME = "cfe_nom"

# Set up access for public S3 bucket
session = botocore.session.get_session()
s3 = session.create_client(
    's3',
    config=Config(signature_version=UNSIGNED)
)


@flow(
    flow_run_name="ingest-datastream-forecasts",
    timeout_seconds=60 * 60
)
def ingest_datastream_forecasts(
    temp_dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp, None] = None,
    num_lookback_days: int = LOOKBACK_DAYS,
    forecast_configuration: str = FORECAST_CONFIGURATION,
    hydrofabric_version: str = HYDROFABRIC_VERSION,
    datastream_name: str = DATASTREAM_NAME,
    start_spark_cluster: bool = True,
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

    if end_dt is None:
        end_dt = datetime.now(UTC)
    elif isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    start_dt = end_dt - timedelta(days=num_lookback_days)
    yrmoday = start_dt.strftime("%Y%m%d")
    logger.info(f"Processing DataStream forecasts for date: {yrmoday}")

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster
    )

    # Limit secondary IDs to USGS sites that are active and have discharge data
    locations_sdf = ev.location_attributes_view(
            attr_list=["is_active", "has_inst_discharge"]
    ).filter(
        filters=[
            {
                "column": "location_id",
                "operator": "like",
                "value": "usgs-%"
            },
            "is_active = 'True'",
            "has_inst_discharge = 'True'"
        ]
    ).to_sdf()
    # Filter crosswalks to 'nrds22-' secondary IDs whose primary_location_id is an active USGS site
    filtered_crosswalks_sdf = (
        ev.location_crosswalks.to_sdf()
        .filter(F.col("secondary_location_id").startswith("nrds22-"))
        .join(
            locations_sdf.select(F.col("location_id").alias("primary_location_id")),
            on="primary_location_id",
            how="inner"
        )
    )
    stripped_ids = [
        int(row[0].split("-")[1])
        for row in filtered_crosswalks_sdf.select("secondary_location_id").collect()
    ]

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

    configuration_name = f"nrds_v22_{datastream_name.replace('_', '')}_{forecast_configuration}"

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
            unit_name=UNIT_NAME,
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
    #         unit_name=UNIT_NAME,
    #         variable_name=VARIABLE_NAME,
    #         configuration_name=configuration_name,
    #         location_id_prefix=LOCATION_ID_PREFIX,
    #     )
    #     futures.append(future)
    # wait(futures)

    # # Coalesce cache files for optimized loading
    # coalesced_cache_dir = output_cache_dir / "coalesced"
    # coalesce_cache_files(
    #     ev=ev,
    #     num_cache_files=num_cache_files,
    #     output_cache_dir=output_cache_dir,
    #     coalesced_cache_dir=coalesced_cache_dir
    # )

    # Load output
    load_to_warehouse(
        ev=ev,
        in_path=output_cache_dir,
        table_name="secondary_timeseries"
    )
