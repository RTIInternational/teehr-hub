from pathlib import Path
from typing import Union
import logging

from prefect import flow, get_run_logger

from workflows.utils.common_utils import initialize_evaluation, set_table_properties, table_exists
from update_joined_forecasts import JOINED_FORECAST_TABLE_NAME
from utils.forecast_utils import (
    write_forecast_metrics_by_lead_time_bins,
    write_forecast_metrics_by_location,
    FORECAST_BY_LEAD_TIME_BIN_GROUPBY,
    FORECAST_BY_LOCATION_GROUPBY,
    FORECAST_METRICS
)

logging.getLogger("teehr").setLevel(logging.INFO)

DEFAULT_SHUFFLE_PARTITIONS = 256
METRICS_BY_LEAD_TIME_TABLE_NAME = "fcst_metrics_by_lead_time_bins"
METRICS_BY_LOCATION_TABLE_NAME = "fcst_metrics_by_location"
METRIC_COL_NAMES = [metric.output_field_name for metric in FORECAST_METRICS]


@flow(
    flow_run_name="update-forecast-metrics-table",
    timeout_seconds=60 * 60
)
def update_forecast_metrics_table(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 8,
    executor_cores: int = 4,
    executor_memory: str = "32g"
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
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
        update_configs={
            "spark.sql.shuffle.partitions": str(DEFAULT_SHUFFLE_PARTITIONS),
        }
    )

    logger.info("Calculating and writing forecast metrics by lead time bins...")
    lead_time_write_mode = (
        "overwrite"
        if table_exists(ev=ev, table_name=METRICS_BY_LEAD_TIME_TABLE_NAME)
        else "create_or_replace"
    )
    write_forecast_metrics_by_lead_time_bins(
        ev=ev,
        joined_forecast_table_name=JOINED_FORECAST_TABLE_NAME,
        output_table_name=METRICS_BY_LEAD_TIME_TABLE_NAME,
        write_mode=lead_time_write_mode
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

    logger.info("Calculating and writing forecast metrics by location...")
    location_write_mode = (
        "overwrite"
        if table_exists(ev=ev, table_name=METRICS_BY_LOCATION_TABLE_NAME)
        else "create_or_replace"
    )
    write_forecast_metrics_by_location(
        ev=ev,
        joined_forecast_table_name=JOINED_FORECAST_TABLE_NAME,
        output_table_name=METRICS_BY_LOCATION_TABLE_NAME,
        write_mode=location_write_mode
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
