import os
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from typing import Union
import logging

from prefect import flow, get_run_logger
import pandas as pd

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session
from teehr.fetching.utils import format_nwm_configuration_metadata

# Start up a local Dask cluster
from dask.distributed import Client
client = Client()

logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now()
LOOKBACK_DAYS = 1


@flow(flow_run_name="ingest-nwm-streamflow-forecasts")
def ingest_nwm_streamflow_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: Union[int, None] = None,
    nwm_configuration: str = "short_range",
    nwm_version: str = "nwm30",
    output_type: str = "channel_rt",
    variable_name: str = "streamflow"
) -> None:
    """NWM Streamflow Forecasts Ingestion.

    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing NWM forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    """
    logger = get_run_logger()

    spark = create_spark_session()

    ev = teehr.Evaluation(
        spark=spark,
        dir_path=dir_path,
        check_evaluation_version=False
    )
    ev.set_active_catalog("remote")

    # Format the NWM configuration name for TEEHR
    teehr_nwm_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version
    )
    if num_lookback_days is None:
        latest_nwm_reference_time = ev.spark.sql(f"""
            SELECT MAX(reference_time) as latest_reference_time
            FROM iceberg.teehr.secondary_timeseries
            WHERE configuration_name = '{teehr_nwm_config["name"]}'
        """).collect()
        if len(latest_nwm_reference_time) > 0:
            latest_nwm_reference_time = latest_nwm_reference_time[0].asDict()["latest_reference_time"]
            start_dt = latest_nwm_reference_time + timedelta(minutes=1)
        else:
            start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    else:
        start_dt = end_dt - timedelta(days=num_lookback_days)

    ev.fetch.nwm_operational_points(
        start_date=start_dt,
        end_date=end_dt,
        nwm_configuration=nwm_configuration,
        nwm_version=nwm_version,
        output_type=output_type,
        variable_name=variable_name
    )
    ev.spark.stop()
