from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
import logging

import pandas as pd
import teehr
from prefect import get_run_logger, task
from prefect.cache_policies import NO_CACHE
from teehr.models.filters import TableFilter

logging.getLogger("teehr").setLevel(logging.INFO)

JOINED_FORECAST_TABLE_NAME = "fcst_joined_timeseries"
JOINED_FORECAST_UNIQUENESS_FIELDS = [
    "reference_time",
    "value_time",
    "primary_location_id",
    "secondary_location_id",
    "configuration_name",
    "unit_name",
    "variable_name",
    "member",
]
JOINED_FORECAST_NULLABLE_FIELDS = ["member"]
JOINED_FORECAST_PARTITION_BY = ["months(value_time)", "configuration_name"]
JOINED_FORECAST_WRITE_ORDERED_BY = [
    "primary_location_id",
    "secondary_location_id",
    "reference_time",
    "value_time",
]
JOINED_FORECAST_CHECKPOINT_TABLE_NAME = "workflow_state_joined_forecasts"


def _format_config_names(configuration_names: list[str]) -> str:
    return ", ".join(f"'{name}'" for name in configuration_names)


def _serialize_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).isoformat()


def _deserialize_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    return pd.Timestamp(value).to_pydatetime()


@task(cache_policy=NO_CACHE)
def plan_backfill_batches(
    ev: teehr.Evaluation,
    forecast_configuration_names: list[str],
    batch_by_month: bool = True,
) -> list[dict[str, Any]]:
    """Plan joined forecast batches by configuration and value_time month."""
    logger = get_run_logger()

    if not forecast_configuration_names:
        logger.info("No forecast configurations supplied for backfill planning.")
        return []

    config_names_sql = _format_config_names(forecast_configuration_names)
    if not batch_by_month:
        query = f"""
            SELECT
                configuration_name,
                MIN(reference_time) AS batch_min_reference_time,
                MAX(reference_time) AS batch_max_reference_time,
                MIN(value_time) AS batch_min_value_time,
                MAX(value_time) AS batch_max_value_time,
                COUNT(*) AS batch_row_count
            FROM iceberg.teehr.secondary_timeseries
            WHERE configuration_name IN ({config_names_sql})
            GROUP BY configuration_name
            ORDER BY configuration_name
        """
    else:
        query = f"""
            SELECT
                configuration_name,
                date_trunc('month', value_time) AS batch_month,
                MIN(reference_time) AS batch_min_reference_time,
                MAX(reference_time) AS batch_max_reference_time,
                MIN(value_time) AS batch_min_value_time,
                MAX(value_time) AS batch_max_value_time,
                COUNT(*) AS batch_row_count
            FROM iceberg.teehr.secondary_timeseries
            WHERE configuration_name IN ({config_names_sql})
            GROUP BY configuration_name, date_trunc('month', value_time)
            ORDER BY configuration_name, batch_month
        """

    rows = ev.spark.sql(query).toPandas().to_dict("records")
    logger.info("Planned %s backfill batches.", len(rows))
    return rows


@task(cache_policy=NO_CACHE)
def get_incremental_checkpoint(
    ev: teehr.Evaluation,
    workflow_name: str,
    checkpoint_table_name: str = JOINED_FORECAST_CHECKPOINT_TABLE_NAME,
) -> datetime | None:
    """Read the last successful joined-forecast checkpoint we control."""
    logger = get_run_logger()
    table_name = f"iceberg.teehr.{checkpoint_table_name}"
    if not ev.spark.catalog.tableExists(table_name):
        logger.info("Checkpoint table %s does not exist yet.", checkpoint_table_name)
        return None

    rows = ev.spark.sql(
        f"""
        SELECT checkpoint_ts
        FROM {table_name}
        WHERE workflow_name = '{workflow_name}'
        LIMIT 1
        """
    ).collect()
    if not rows:
        logger.info("No checkpoint found for workflow %s.", workflow_name)
        return None

    checkpoint = _deserialize_timestamp(rows[0]["checkpoint_ts"])
    if checkpoint is None:
        logger.info("Checkpoint row exists but no timestamp found for %s.", workflow_name)
        return None

    logger.info(
        "Using stored checkpoint for %s: %s",
        workflow_name,
        pd.Timestamp(checkpoint).isoformat(),
    )
    return checkpoint


@task(cache_policy=NO_CACHE)
def upsert_incremental_checkpoint(
    ev: teehr.Evaluation,
    workflow_name: str,
    checkpoint_ts: datetime,
    checkpoint_table_name: str = JOINED_FORECAST_CHECKPOINT_TABLE_NAME,
) -> None:
    """Persist the last successful joined-forecast checkpoint."""
    logger = get_run_logger()
    checkpoint_df = pd.DataFrame(
        {
            "workflow_name": [workflow_name],
            "checkpoint_ts": [pd.Timestamp(checkpoint_ts)],
            "updated_at": [pd.Timestamp.utcnow().tz_localize(None)],
        }
    )
    ev._write.to_warehouse(
        source_data=checkpoint_df,
        table_name=checkpoint_table_name,
        write_mode=(
            "upsert"
            if ev.spark.catalog.tableExists(
                f"iceberg.teehr.{checkpoint_table_name}"
            )
            else "create_or_replace"
        ),
        uniqueness_fields=["workflow_name"],
    )
    logger.info(
        "Updated checkpoint for %s to %s.",
        workflow_name,
        pd.Timestamp(checkpoint_ts).isoformat(),
    )


@task(cache_policy=NO_CACHE)
def plan_incremental_batches(
    ev: teehr.Evaluation,
    forecast_configuration_names: list[str],
    changed_since: datetime,
    batch_by_month: bool = True,
) -> list[dict[str, Any]]:
    """Plan incremental batches from changed forecasts and changed observations.

    This planner combines two incremental signals:

    1. Forecast rows in ``secondary_timeseries`` whose ``created_at`` or
       ``updated_at`` is newer than ``changed_since``.
    2. Forecast rows whose ``value_time`` overlaps observations in
       ``primary_timeseries`` that changed since ``changed_since``.

    The second signal handles the common case where forecasts were already
    loaded earlier but observations arrive later, so the joined table needs to
    be refreshed even though the forecast rows themselves did not change.

    The primary-side detection is intentionally coarse: it collapses changed
    observations to a single min/max ``value_time`` window and then marks all
    forecasts overlapping that window as impacted. That is safe and keeps the
    planner simple, but it can over-reprocess more forecasts than strictly
    necessary when changed observations are sparse across a large time span.

    Planned batches are grouped by ``configuration_name`` and, when
    ``batch_by_month`` is True, by ``date_trunc('month', value_time)`` so the
    subsequent join can prune both primary and secondary tables on the same
    ``value_time`` axis used by the join itself.
    """
    logger = get_run_logger()

    if not forecast_configuration_names:
        logger.info("No forecast configurations supplied for incremental planning.")
        return []

    changed_since_literal = pd.Timestamp(changed_since).isoformat(sep=" ")
    config_names_sql = _format_config_names(forecast_configuration_names)

    if not batch_by_month:
        batch_select = """
            s.configuration_name AS configuration_name,
            MIN(s.reference_time) AS batch_min_reference_time,
            MAX(s.reference_time) AS batch_max_reference_time,
            MIN(s.value_time) AS batch_min_value_time,
            MAX(s.value_time) AS batch_max_value_time,
            COUNT(*) AS batch_row_count
        """
        batch_group_by = "s.configuration_name"
        batch_order_by = "configuration_name"
    else:
        batch_select = """
            s.configuration_name AS configuration_name,
            date_trunc('month', s.value_time) AS batch_month,
            MIN(s.reference_time) AS batch_min_reference_time,
            MAX(s.reference_time) AS batch_max_reference_time,
            MIN(s.value_time) AS batch_min_value_time,
            MAX(s.value_time) AS batch_max_value_time,
            COUNT(*) AS batch_row_count
        """
        batch_group_by = "s.configuration_name, date_trunc('month', s.value_time)"
        batch_order_by = "configuration_name, batch_month"

    query = f"""
        WITH changed_secondary AS (
            SELECT
                configuration_name,
                reference_time,
                value_time
            FROM iceberg.teehr.secondary_timeseries
            WHERE configuration_name IN ({config_names_sql})
                AND (
                    created_at >= TIMESTAMP '{changed_since_literal}'
                    OR updated_at >= TIMESTAMP '{changed_since_literal}'
                )
        ),
        changed_primary_window AS (
            SELECT
                MIN(value_time) AS min_value_time,
                MAX(value_time) AS max_value_time
            FROM iceberg.teehr.primary_timeseries
            WHERE
                created_at >= TIMESTAMP '{changed_since_literal}'
                OR updated_at >= TIMESTAMP '{changed_since_literal}'
        ),
        impacted_by_primary AS (
            SELECT
                s.configuration_name,
                s.reference_time,
                s.value_time
            FROM iceberg.teehr.secondary_timeseries s
            CROSS JOIN changed_primary_window p
            WHERE configuration_name IN ({config_names_sql})
                AND p.min_value_time IS NOT NULL
                AND s.value_time >= p.min_value_time
                AND s.value_time <= p.max_value_time
        ),
        impacted_secondary AS (
            SELECT * FROM changed_secondary
            UNION
            SELECT * FROM impacted_by_primary
        )
        SELECT
            {batch_select}
        FROM impacted_secondary s
        GROUP BY {batch_group_by}
        ORDER BY {batch_order_by}
    """

    rows = ev.spark.sql(query).toPandas().to_dict("records")
    logger.info("Planned %s incremental batches.", len(rows))
    return rows


def build_primary_filters(batch: dict[str, Any]) -> list[TableFilter]:
    """Build primary filters for a joined forecast batch."""
    filters = []
    if batch.get("batch_min_value_time") is not None:
        filters.append(
            TableFilter(
                column="value_time",
                operator=">=",
                value=batch["batch_min_value_time"],
            )
        )
    if batch.get("batch_max_value_time") is not None:
        filters.append(
            TableFilter(
                column="value_time",
                operator="<=",
                value=batch["batch_max_value_time"],
            )
        )
    return filters


def build_secondary_filters(batch: dict[str, Any]) -> list[TableFilter]:
    """Build secondary filters for a joined forecast batch."""
    filters: list[TableFilter] = [
        TableFilter(
            column="configuration_name",
            operator="=",
            value=batch["configuration_name"],
        )
    ]
    if batch.get("batch_min_value_time") is not None:
        filters.append(
            TableFilter(
                column="value_time",
                operator=">=",
                value=batch["batch_min_value_time"],
            )
        )
    if batch.get("batch_max_value_time") is not None:
        filters.append(
            TableFilter(
                column="value_time",
                operator="<=",
                value=batch["batch_max_value_time"],
            )
        )
    return filters


@task(cache_policy=NO_CACHE)
def write_joined_forecast_batch(
    ev: teehr.Evaluation,
    batch: dict[str, Any],
    table_name: str,
    write_mode: str,
) -> None:
    """Materialize one joined forecast batch to the target table."""
    logger = get_run_logger()
    logger.info(
        "Writing joined forecast batch for configuration=%s ref_time=[%s, %s] value_time=[%s, %s] mode=%s",
        batch["configuration_name"],
        _serialize_timestamp(batch.get("batch_min_reference_time")),
        _serialize_timestamp(batch.get("batch_max_reference_time")),
        _serialize_timestamp(batch.get("batch_min_value_time")),
        _serialize_timestamp(batch.get("batch_max_value_time")),
        write_mode,
    )

    ev.joined_timeseries_view(
        primary_filters=build_primary_filters(batch),
        secondary_filters=build_secondary_filters(batch),
    ).write_to(
        table_name=table_name,
        write_mode=write_mode,
        uniqueness_fields=JOINED_FORECAST_UNIQUENESS_FIELDS,
        nullable_fields=JOINED_FORECAST_NULLABLE_FIELDS,
        partition_by=JOINED_FORECAST_PARTITION_BY,
        write_ordered_by=JOINED_FORECAST_WRITE_ORDERED_BY,
    )


def apply_safety_lookback(
    checkpoint: datetime | None,
    lookback_hours: int,
) -> datetime | None:
    """Apply a rolling safety lookback to a stored checkpoint."""
    if checkpoint is None:
        return None
    return checkpoint - timedelta(hours=lookback_hours)