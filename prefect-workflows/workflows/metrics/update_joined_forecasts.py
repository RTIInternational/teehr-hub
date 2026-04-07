from pathlib import Path
import shutil
from typing import Union, List
import logging

from prefect import flow, get_run_logger

# from utils.forecast_utils import join_forecast_timeseries
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
    "nrds_v22_lstm0_medium_range",
    "nwpsrfc_streamflow_forecast"
]
JOINED_FORECAST_TABLE_NAME = "fcst_joined_timeseries"


@flow(
    flow_run_name="update-joined-forecast-table",
    timeout_seconds=60 * 60,
    retries=2
)
def update_joined_forecast_table(
    temp_dir_path: Union[str, Path],
    forecast_configuration_names: List[str] =
        FORECAST_CONFIGURATION_NAMES,
    start_spark_cluster: bool = True,
) -> None:
    """Create the joined forecast table.

    Includes filters to limit the join to forecast configurations.
    """
    logger = get_run_logger()
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=8
    )
    # Find the min reference time across all forecast configurations
    names = ", ".join(f"'{n}'" for n in forecast_configuration_names)
    query = f"""
    SELECT MIN(reference_time) AS global_min_reference_time
    FROM iceberg.teehr.secondary_timeseries
    WHERE configuration_name IN ({names})
    """
    min_ref_time = ev.spark.sql(query).collect()[0]["global_min_reference_time"]
    min_ref_time_str = min_ref_time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Global minimum reference time: {min_ref_time_str}")

    logger.info("Creating joined forecast timeseries table...")
    primary_filters = [f"value_time >= '{min_ref_time_str}'"]
    secondary_filters=[
        {
            "column": "configuration_name",
            "operator": "in",
            "value": forecast_configuration_names
        },
        f"value_time >= '{min_ref_time_str}'"
    ]
    ev.joined_timeseries_view(
        primary_filters=primary_filters,
        secondary_filters=secondary_filters
    ).write_to(
        table_name=JOINED_FORECAST_TABLE_NAME,
        write_mode="create_or_replace"
    )
    logger.info(
        f"Joined forecast timeseries table written to warehouse as"
        f" {JOINED_FORECAST_TABLE_NAME}."
    )
