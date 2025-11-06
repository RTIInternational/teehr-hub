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

    # Task? Get latest for all locations
    latest_usgs_value_time = ev.spark.sql("""
        SELECT value_time, location_id
        FROM iceberg.teehr.primary_timeseries
        WHERE 
            configuration_name = 'usgs_observations'
        ORDER BY value_time DESC
        LIMIT 1
    ;""").collect()
    if len(latest_usgs_value_time) > 0:
        latest_usgs_value_time = latest_usgs_value_time[0].asDict()["value_time"]
        start_dt = latest_usgs_value_time + timedelta(minutes=1)
    else:
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)

    ev.fetch.usgs_streamflow(
        start_date=start_dt,
        end_date=end_dt
    )
    ev.spark.stop()
