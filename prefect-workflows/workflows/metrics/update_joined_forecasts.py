from pathlib import Path
from datetime import datetime, UTC
from typing import Union, List
import logging

from prefect import flow, get_run_logger

from workflows.utils.common_utils import initialize_evaluation
from utils.joined_forecast_utils import (
    JOINED_FORECAST_TABLE_NAME,
    apply_safety_lookback,
    get_incremental_checkpoint,
    plan_backfill_batches,
    plan_incremental_batches,
    upsert_incremental_checkpoint,
    write_joined_forecast_batch,
)

logging.getLogger("teehr").setLevel(logging.INFO)

FORECAST_CONFIGURATION_NAMES = [
    "nwm30_short_range",
    "nwm30_medium_range",
    "nrds_v22_cfenom_medium_range",
    "nrds_v22_cfenom_short_range",
    "nrds_v22_lstm0_short_range",
    "nrds_v22_lstm0_medium_range",
    "nwpsrfc_streamflow_forecast"
]
DEFAULT_SHUFFLE_PARTITIONS = 256
DEFAULT_INCREMENTAL_LOOKBACK_HOURS = 2
JOINED_FORECAST_CHECKPOINT_NAME = "fcst_joined_timeseries"


def _initialize_joined_forecast_evaluation(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool,
    executor_instances: int,
    executor_cores: int,
    executor_memory: str,
):
    return initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
        update_configs={
            "spark.sql.shuffle.partitions": str(DEFAULT_SHUFFLE_PARTITIONS),
        }
    )


@flow(
    flow_run_name="update-joined-forecast-table",
    timeout_seconds=60 * 60 * 3,
    retries=2
)
def update_joined_forecast_table(
    temp_dir_path: Union[str, Path],
    forecast_configuration_names: List[str] = FORECAST_CONFIGURATION_NAMES,
    start_spark_cluster: bool = True,
    executor_instances: int = 24,
    executor_cores: int = 4,
    executor_memory: str = "32g",
    batch_size_months: int = 24,
) -> None:
    """Create the joined forecast table using bounded backfill batches.

    Batches work by configuration_name and configurable value_time month windows.
    """
    logger = get_run_logger()
    ev = _initialize_joined_forecast_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )
    batches = plan_backfill_batches(
        ev=ev,
        forecast_configuration_names=forecast_configuration_names,
        batch_size_months=batch_size_months,
    )

    if not batches:
        logger.info("No joined forecast backfill batches were planned.")
        return

    logger.info("Writing %s joined forecast backfill batches.", len(batches))
    for index, batch in enumerate(batches):
        if index == 0:
            write_mode = "create_or_replace"
        else:
            write_mode = "append"

        write_joined_forecast_batch(
            ev=ev,
            batch=batch,
            table_name=JOINED_FORECAST_TABLE_NAME,
            write_mode=write_mode,
        )
    upsert_incremental_checkpoint(
        ev=ev,
        workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
        checkpoint_ts=datetime.now(UTC).replace(tzinfo=None),
    )
    logger.info(
        f"Joined forecast timeseries table written to warehouse as"
        f" {JOINED_FORECAST_TABLE_NAME}."
    )


@flow(
    flow_run_name="update-joined-forecast-table-incremental",
    timeout_seconds=60 * 60,
    retries=2,
)
def update_joined_forecast_table_incremental(
    temp_dir_path: Union[str, Path],
    forecast_configuration_names: List[str] = FORECAST_CONFIGURATION_NAMES,
    start_spark_cluster: bool = True,
    executor_instances: int = 8,
    executor_cores: int = 4,
    executor_memory: str = "32g",
    batch_size_months: int = 1,
    safety_lookback_hours: int = DEFAULT_INCREMENTAL_LOOKBACK_HOURS,
    changed_since: Union[str, datetime, None] = None,
) -> None:
    """Incrementally upsert joined forecast batches affected by source changes."""
    logger = get_run_logger()
    ev = _initialize_joined_forecast_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )

    if isinstance(changed_since, str):
        checkpoint = datetime.fromisoformat(changed_since)
    else:
        checkpoint = changed_since

    if checkpoint is None:
        checkpoint = get_incremental_checkpoint(
            ev=ev,
            workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
        )
        checkpoint = apply_safety_lookback(checkpoint, safety_lookback_hours)

    if checkpoint is None:
        logger.info(
            "No incremental checkpoint exists yet. Falling back to batched backfill."
        )
        batches = plan_backfill_batches(
            ev=ev,
            forecast_configuration_names=forecast_configuration_names,
            batch_size_months=batch_size_months,
        )
        for index, batch in enumerate(batches):
            if index == 0:
                write_mode = "create_or_replace"
            else:
                write_mode = "append"

            write_joined_forecast_batch(
                ev=ev,
                batch=batch,
                table_name=JOINED_FORECAST_TABLE_NAME,
                write_mode=write_mode,
            )
        upsert_incremental_checkpoint(
            ev=ev,
            workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
            checkpoint_ts=datetime.now(UTC).replace(tzinfo=None),
        )
        return

    batches = plan_incremental_batches(
        ev=ev,
        forecast_configuration_names=forecast_configuration_names,
        changed_since=checkpoint,
        batch_size_months=batch_size_months,
    )
    if not batches:
        logger.info("No joined forecast incremental batches were planned.")
        upsert_incremental_checkpoint(
            ev=ev,
            workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
            checkpoint_ts=datetime.now(UTC).replace(tzinfo=None),
        )
        return

    logger.info("Writing %s joined forecast incremental batches.", len(batches))
    for batch in batches:
        write_joined_forecast_batch(
            ev=ev,
            batch=batch,
            table_name=JOINED_FORECAST_TABLE_NAME,
            write_mode="upsert",
        )
    upsert_incremental_checkpoint(
        ev=ev,
        workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
        checkpoint_ts=datetime.now(UTC).replace(tzinfo=None),
    )
