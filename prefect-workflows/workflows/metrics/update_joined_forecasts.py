from pathlib import Path
import shutil
from typing import Union, List
import logging

from prefect import flow, get_run_logger

from utils.forecast_utils import join_forecast_timeseries
from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)

FORECAST_CONFIGURATION_NAMES = [
    "nwm30_short_range",
    "nwm30_medium_range",
    "nrds_v22_cfenom_medium_range",
    "nrds_v22_cfenom_short_range",
    "nrds_v22_lstm_short_range",
    "nrds_v22_lstm_medium_range",
    "nrds_v22_lstm0_short_range",
    "nrds_v22_lstm0_medium_range"
]
JOINED_FORECAST_TABLE_NAME = "fcst_joined_timeseries"


@flow(
    flow_run_name="update-joined-forecast-table",
    timeout_seconds=60 * 60,
    retries=2
)
def update_joined_forecast_table(
    dir_path: Union[str, Path],
    forecast_configuration_names: List[str] =
        FORECAST_CONFIGURATION_NAMES
) -> None:
    """Create the joined forecast table

    Notes
    -----
    - Ultimately the join will be updated to include a filter so
      so that recent data can be joined and appended to the existing table.
    - Currently, the entire joined table is re-created each time.
    """
    logger = get_run_logger()
    ev = initialize_evaluation(
        dir_path=dir_path,
        start_spark_cluster=True,
        executor_instances=8,
        executor_cores=8,
        executor_memory="50g",
        update_configs={
            "spark.local.dir": "/data/tmp/spark-temp"
        }
    )

    logger.info("Joining forecast timeseries...")
    joined_sdf = join_forecast_timeseries(
        ev=ev,
        forecast_configuration_names=forecast_configuration_names
    )

    logger.info("Writing joined forecast timeseries table to warehouse...")
    # Note. We could append to joined_timeseries here instead
    # of recreating a new table.
    ev.write.to_warehouse(
        source_data=joined_sdf,
        table_name=JOINED_FORECAST_TABLE_NAME,
        write_mode="create_or_replace"
    )
    logger.info(
        f"Joined forecast timeseries table written to warehouse as"
        f" {JOINED_FORECAST_TABLE_NAME}."
    )
    # Cleanup Spark temp data
    shutil.rmtree("/data/tmp/spark-temp", ignore_errors=True)
