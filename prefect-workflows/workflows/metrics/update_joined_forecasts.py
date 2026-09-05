from pathlib import Path
from datetime import datetime, UTC
from typing import Union, List
import logging

from prefect import flow, get_run_logger

from workflows.utils.common_utils import initialize_evaluation
from workflows.utils.time_utils import to_naive_utc
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
    "nwpsrfc_streamflow_forecast",
    "nwm30_short_range_alaska",
    "nwm30_short_range_hawaii",
    "nwm30_short_range_puertorico",
    "nwm30_medium_range_alaska",
    "nwm30_medium_range_blend",
    "nwm30_medium_range_blend_alaska"
]
DEFAULT_SHUFFLE_PARTITIONS = 256
DEFAULT_INCREMENTAL_LOOKBACK_HOURS = 2
JOINED_FORECAST_CHECKPOINT_NAME = "fcst_joined_timeseries"
WAREHOUSE_TABLE_PREFIX = "iceberg.teehr"


def _initial_backfill_write_mode(
    ev,
    table_name: str,
    replace_existing_table: bool,
) -> str:
    """Choose first-write behavior for staged backfills.

    If the target table already exists and replacement is not explicitly requested,
    start in append mode so chunked runs can safely accumulate data across
    configuration subsets.
    """
    if replace_existing_table:
        return "create_or_replace"

    table_exists = ev.spark.catalog.tableExists(f"{WAREHOUSE_TABLE_PREFIX}.{table_name}")
    return "append" if table_exists else "create_or_replace"


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


def _checkpoint_advance_blocker(
    forecast_configuration_names: List[str],
    effective_changed_since: Union[datetime, None] = None,
    stored_checkpoint: Union[datetime, None] = None,
) -> Union[str, None]:
    """Explain why the shared checkpoint must not advance, or None if it may.

    The checkpoint is a single row standing for every configuration, so moving
    it forward after a run that only looked at part of the source data silently
    strands the changes that run never considered -- they fall behind the
    checkpoint and are never picked up again.
    """
    missing = sorted(
        set(FORECAST_CONFIGURATION_NAMES) - set(forecast_configuration_names)
    )
    if missing:
        return f"run covered only a subset of configurations (missing: {missing})"

    if (
        stored_checkpoint is not None
        and effective_changed_since is not None
        and effective_changed_since > stored_checkpoint
    ):
        return (
            f"changed_since ({effective_changed_since.isoformat()}) is later than "
            f"the stored checkpoint ({stored_checkpoint.isoformat()}), so source "
            "changes between the two were never processed"
        )

    return None


def _advance_checkpoint_if_complete(
    ev,
    logger,
    forecast_configuration_names: List[str],
    effective_changed_since: Union[datetime, None] = None,
    stored_checkpoint: Union[datetime, None] = None,
) -> None:
    """Advance the shared checkpoint only if this run covered everything."""
    blocker = _checkpoint_advance_blocker(
        forecast_configuration_names=forecast_configuration_names,
        effective_changed_since=effective_changed_since,
        stored_checkpoint=stored_checkpoint,
    )
    if blocker is not None:
        logger.warning(
            "Leaving the %s checkpoint where it is: %s. Run the full configuration "
            "set to move it forward.",
            JOINED_FORECAST_CHECKPOINT_NAME,
            blocker,
        )
        return

    upsert_incremental_checkpoint(
        ev=ev,
        workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
        checkpoint_ts=datetime.now(UTC).replace(tzinfo=None),
    )


def _batch_progress_message(batch: dict, index: int, total: int, write_mode: str) -> str:
    """Build a compact per-batch progress message."""
    return (
        "Batch "
        f"{index}/{total} "
        f"config={batch.get('configuration_name')} "
        f"batch_month={batch.get('batch_month')} "
        f"rows={batch.get('batch_row_count')} "
        f"value_time=[{batch.get('batch_min_value_time')}, {batch.get('batch_max_value_time')}] "
        f"mode={write_mode}"
    )


@flow(
    flow_run_name="update-joined-forecast-table",
    timeout_seconds=60 * 60 * 6,
    retries=2
)
def update_joined_forecast_table(
    temp_dir_path: Union[str, Path],
    forecast_configuration_names: List[str] = FORECAST_CONFIGURATION_NAMES,
    start_spark_cluster: bool = True,
    executor_instances: int = 24,
    executor_cores: int = 4,
    executor_memory: str = "32g",
    batch_size_months: int = 3,
    replace_existing_table: bool = True,
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
    first_write_mode = _initial_backfill_write_mode(
        ev=ev,
        table_name=JOINED_FORECAST_TABLE_NAME,
        replace_existing_table=replace_existing_table,
    )
    logger.info(
        "Backfill execution mode selected: first_write_mode=%s replace_existing_table=%s",
        first_write_mode,
        replace_existing_table,
    )
    for index, batch in enumerate(batches):
        write_mode = first_write_mode if index == 0 else "append"
        logger.info(_batch_progress_message(batch, index + 1, len(batches), write_mode))

        write_joined_forecast_batch(
            ev=ev,
            batch=batch,
            table_name=JOINED_FORECAST_TABLE_NAME,
            write_mode=write_mode,
        )
    _advance_checkpoint_if_complete(
        ev=ev,
        logger=logger,
        forecast_configuration_names=forecast_configuration_names,
    )
    logger.info(
        f"Joined forecast timeseries table written to warehouse as"
        f" {JOINED_FORECAST_TABLE_NAME}."
    )


@flow(
    flow_run_name="update-joined-forecast-table-incremental",
    timeout_seconds=60 * 60 * 2,
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
    replace_existing_table_on_backfill_fallback: bool = False,
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

    stored_checkpoint = get_incremental_checkpoint(
        ev=ev,
        workflow_name=JOINED_FORECAST_CHECKPOINT_NAME,
    )

    # None means "no checkpoint given", handled below, so don't default it to now.
    if changed_since is not None:
        checkpoint = to_naive_utc(changed_since)
    else:
        checkpoint = apply_safety_lookback(stored_checkpoint, safety_lookback_hours)

    if checkpoint is None:
        logger.info(
            "No incremental checkpoint exists yet. Falling back to batched backfill."
        )
        batches = plan_backfill_batches(
            ev=ev,
            forecast_configuration_names=forecast_configuration_names,
            batch_size_months=batch_size_months,
        )

        first_write_mode = _initial_backfill_write_mode(
            ev=ev,
            table_name=JOINED_FORECAST_TABLE_NAME,
            replace_existing_table=replace_existing_table_on_backfill_fallback,
        )
        logger.info(
            "Incremental fallback execution mode selected: first_write_mode=%s replace_existing_table_on_backfill_fallback=%s",
            first_write_mode,
            replace_existing_table_on_backfill_fallback,
        )

        for index, batch in enumerate(batches):
            write_mode = first_write_mode if index == 0 else "append"
            logger.info(_batch_progress_message(batch, index + 1, len(batches), write_mode))

            write_joined_forecast_batch(
                ev=ev,
                batch=batch,
                table_name=JOINED_FORECAST_TABLE_NAME,
                write_mode=write_mode,
            )
        _advance_checkpoint_if_complete(
            ev=ev,
            logger=logger,
            forecast_configuration_names=forecast_configuration_names,
            effective_changed_since=checkpoint,
            stored_checkpoint=stored_checkpoint,
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
        _advance_checkpoint_if_complete(
            ev=ev,
            logger=logger,
            forecast_configuration_names=forecast_configuration_names,
            effective_changed_since=checkpoint,
            stored_checkpoint=stored_checkpoint,
        )
        return

    logger.info("Writing %s joined forecast incremental batches.", len(batches))
    for index, batch in enumerate(batches):
        logger.info(_batch_progress_message(batch, index + 1, len(batches), "upsert"))
        write_joined_forecast_batch(
            ev=ev,
            batch=batch,
            table_name=JOINED_FORECAST_TABLE_NAME,
            write_mode="upsert",
        )
    _advance_checkpoint_if_complete(
        ev=ev,
        logger=logger,
        forecast_configuration_names=forecast_configuration_names,
        effective_changed_since=checkpoint,
        stored_checkpoint=stored_checkpoint,
    )
