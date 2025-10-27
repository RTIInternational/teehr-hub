import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from typing import Union

from prefect import flow
import pandas as pd

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session
from teehr.fetching.utils import format_nwm_configuration_metadata

# Start up a local Dask cluster
from dask.distributed import Client
client = Client()


LOCAL_EV_DIR = "/data/temp_warehouse"
CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1


@flow(flow_run_name="ingest_nwm_streamflow_forecasts-{name}", log_prints=True)
def ingest_nwm_streamflow_forecasts(
    local_dir_path: Union[str, Path] = LOCAL_EV_DIR,
    start_dt: Union[str, datetime, pd.Timestamp] = None,
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    nwm_configuration: str = "short_range",
    nwm_version: str = "nwm30",
    output_type: str = "channel_rt",
    variable_name: str = "streamflow"
) -> None:
    """NWM Streamflow Forecasts Ingestion."""
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
    
    # Format the NWM configuration name for TEEHR
    teehr_nwm_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version
    )
    latest_nwm_reference_time = ev.spark.sql(f"""
        SELECT reference_time, location_id
        FROM iceberg.teehr.secondary_timeseries
        WHERE 
            configuration_name = '{teehr_nwm_config["name"]}'
        LIMIT 1
    ;""").collect()
    if len(latest_nwm_reference_time) > 0:
        latest_nwm_reference_time = latest_nwm_reference_time[0].asDict()["reference_time"]
        start_dt = latest_nwm_reference_time + timedelta(minutes=1)
    else:
        start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
        
    ev.fetch.nwm_operational_points(
        start_date=start_dt,
        end_date=end_dt,
        nwm_configuration=nwm_configuration,
        nwm_version=nwm_version,
        output_type=output_type,
        variable_name=variable_name
    )
    ev.spark.stop()