from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger
import pandas as pd

from teehr.fetching.utils import format_nwm_configuration_metadata
from workflows.utils.common_utils import initialize_evaluation, cleanup_temp_teehr_dir_flow

# Start up a local Dask cluster
from dask.distributed import Client
client = Client()

logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now(UTC).replace(tzinfo=None)
LOOKBACK_DAYS = 1


@flow(
    flow_run_name="ingest-nwm-streamflow-forecasts",
    timeout_seconds=60 * 60
)
def ingest_nwm_streamflow_forecasts(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    nwm_configuration: str = "short_range",
    nwm_version: str = "nwm30",
    output_type: str = "channel_rt",
    variable_name: str = "streamflow"
) -> None:
    """NWM Streamflow Forecasts Ingestion.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing NWM forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    ev = initialize_evaluation(dir_path=dir_path)

    # Format the NWM configuration name for TEEHR
    teehr_nwm_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version
    )
    if num_lookback_days is None:
        logger.info(
            "No lookback days provided, determining start date from latest"
            " NWM reference time"
        )
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
        logger.info(
            f"Setting start date to {num_lookback_days} days before end date"
        )
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

    cleanup_temp_teehr_dir_flow(path=ev.dir_path)