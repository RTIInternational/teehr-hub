import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from typing import Union
import logging

from prefect import flow, get_run_logger
import pandas as pd

import teehr

logging.getLogger("teehr").setLevel(logging.INFO)

from teehr.evaluation.spark_session_utils import create_spark_session


LOCAL_EV_DIR = "/data/temp_warehouse"
CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1
DEFAULT_START_DT = CURRENT_DT - timedelta(days=1)

# Q. Can we keep a spark session running across flows?


@flow(flow_run_name="ingest-usgs-streamflow-obs")
def ingest_usgs_streamflow_obs(
    dir_path: Union[str, Path] = LOCAL_EV_DIR,
    start_dt: Union[str, datetime, pd.Timestamp] = DEFAULT_START_DT,
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT
) -> None:
    """USGS Streamflow Ingestion from NWIS."""
    logger = get_run_logger()

    spark = create_spark_session()
    ev = teehr.Evaluation(
        spark=spark,
        dir_path=dir_path,
        check_evaluation_version=False
    )
    ev.set_active_catalog("remote")

    # Get the earliest of the most recent value_times across all locations
    logger.info("🔍 Finding the earliest of the most recent value_times per location")

    latest_usgs_value_times = ev.spark.sql("""
        WITH latest_per_location AS (
            SELECT
                location_id,
                MAX(value_time) as latest_value_time
            FROM iceberg.teehr.primary_timeseries
            WHERE configuration_name = 'usgs_observations'
            GROUP BY location_id
        )
        SELECT
            MIN(latest_value_time) as earliest_latest_value_time,
            COUNT(*) as location_count
        FROM latest_per_location
    """).collect()

    if len(latest_usgs_value_times) > 0 and latest_usgs_value_times[0]["earliest_latest_value_time"] is not None:
        result = latest_usgs_value_times[0].asDict()
        earliest_latest_value_time = result["earliest_latest_value_time"]
        location_count = result["location_count"]

        start_dt = earliest_latest_value_time + timedelta(minutes=1)

        logger.info(f"📊 Found data for {location_count} locations")
        logger.info(f"📅 Earliest recent value_time: {earliest_latest_value_time}")
        logger.info(f"🚀 Starting ingestion from: {start_dt}")
    else:
        logger.info("📋 No existing USGS observations found, using default lookback")
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
        logger.info(f"📅 Using default start date: {start_dt}")

    logger.info(f"⏰ Fetching USGS data from {start_dt} to {end_dt}")    

    ev.fetch.usgs_streamflow(
        start_date=start_dt,
        end_date=end_dt
    )
    ev.spark.stop()
