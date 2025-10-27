import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from typing import Union

from prefect import flow
import pandas as pd

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session


LOCAL_EV_DIR = "/data/temp_warehouse"
CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1

# Q. Can we keep a spark session running across flows?

@flow(flow_run_name="ingest-usgs-streamflow-obs-{name}", log_prints=True)
def ingest_usgs_streamflow_obs(
    local_dir_path: Union[str, Path] = LOCAL_EV_DIR,
    start_dt: Union[str, datetime, pd.Timestamp] = None,
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT
) -> None:
    """USGS Streamflow Ingestion from NWIS."""
    spark = create_spark_session(
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin123"
    )
    ev = teehr.Evaluation(
        spark=spark,
        dir_path=local_dir_path,
        check_evaluation_version=False
    )
    ev.set_active_catalog("remote")    
    
    # Task? Get latest for all locations
    latest_usgs_value_time = ev.spark.sql(f"""
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