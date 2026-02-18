from pathlib import Path
from typing import Union
import logging

from prefect import flow, get_run_logger

from workflows.utils.common_utils import initialize_evaluation, set_table_properties
from update_joined_forecasts import JOINED_FORECAST_TABLE_NAME
from utils.forecast_utils import (
    calculate_forecast_metrics_by_lead_time_bins,
    calculate_forecast_metrics_by_location,
    FORECAST_BY_LEAD_TIME_BIN_GROUPBY,
    FORECAST_BY_LOCATION_GROUPBY,
    FORECAST_METRICS
)

logging.getLogger("teehr").setLevel(logging.INFO)

METRICS_BY_LEAD_TIME_TABLE_NAME = "fcst_metrics_by_lead_time_bins"
METRICS_BY_LOCATION_TABLE_NAME = "fcst_metrics_by_location"
METRIC_COL_NAMES = [metric.output_field_name for metric in FORECAST_METRICS]


@flow(
    flow_run_name="update-forecast-metrics-table",
    timeout_seconds=60 * 60,
    retries=2
)
def update_forecast_metrics_table(
    dir_path: Union[str, Path]
) -> None:
    """Create the forecast metrics table

    Notes
    -----
    - This requires the joined forecast table to be created first using
      the `update_joined_forecast_table` flow.
    - Currently, the forecast metrics table is re-created each time.
    """
    logger = get_run_logger()

    ev = initialize_evaluation(
        dir_path=dir_path,
        start_spark_cluster=True,
        executor_instances=4,
        executor_cores=3,
        executor_memory="16g",
        update_configs={
            "spark.kubernetes.executor.node.selector.teehr-hub/nodegroup-name": "spark-r5-4xlarge-spot",
            "spark.decommission.enabled": "true",
            "spark.executor.decommission.signal": "SIGTERM",
            "spark.storage.decommission.enabled": "true",
        }
    )

    logger.info("Calculating forecast metrics by lead time bins...")
    sdf = calculate_forecast_metrics_by_lead_time_bins(
        ev=ev,
        joined_forecast_table_name=JOINED_FORECAST_TABLE_NAME,
    )

    logger.info("Writing forecast metrics by lead time bins table to warehouse...")
    ev.write.to_warehouse(
        source_data=sdf,
        table_name=METRICS_BY_LEAD_TIME_TABLE_NAME,
        write_mode="create_or_replace"
    )
    set_table_properties(
        ev=ev,
        table_name=METRICS_BY_LEAD_TIME_TABLE_NAME,
        properties={
            "description": "Forecast metrics by location ID and lead time bins",
            "group_by": ", ".join(FORECAST_BY_LEAD_TIME_BIN_GROUPBY),
            "metrics": ", ".join(METRIC_COL_NAMES)
        }
    )
    logger.info("Forecast metrics by lead time bins table created.")

    logger.info("Calculating forecast metrics by location...")
    sdf = calculate_forecast_metrics_by_location(
        ev=ev,
        joined_forecast_table_name=JOINED_FORECAST_TABLE_NAME,
    )

    logger.info("Writing forecast metrics by location table to warehouse...")
    ev.write.to_warehouse(
        source_data=sdf,
        table_name=METRICS_BY_LOCATION_TABLE_NAME,
        write_mode="create_or_replace"
    )
    set_table_properties(
        ev=ev,
        table_name=METRICS_BY_LOCATION_TABLE_NAME,
        properties={
            "description": "Forecast metrics by location ID",
            "group_by": ", ".join(FORECAST_BY_LOCATION_GROUPBY),
            "metrics": ", ".join(METRIC_COL_NAMES)
        }
    )
    logger.info("Forecast metrics by location table created.")
