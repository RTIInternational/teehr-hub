"""Maintenance for the v1 warehouse's system tables (``iceberg.public``).

The control plane gives new tables their layout (sort order, partitions, file and
row-group sizes), but writes land as they come: unsorted, in many small files. This
flow lays the data out the way run jobs read it -- sorted by series, in files of a
few row groups per series range -- and keeps the tables tidy:

1. layout properties: tables made before the control plane set them get its
   defaults (``LAYOUT_DEFAULTS``; explicit values are kept);
2. sorted rewrite: each partition changed in the last ``days`` (or every one) is
   rewritten whole, in the table's sort order, so its files cover narrow key ranges
   and use the current row-group size;
3. expire snapshots, remove orphan files (failed or retried writes leave them),
   rewrite manifests.

The rewrites change no rows. They don't record lineage (``dataset_writes``): they
are ``replace`` snapshots, which incremental runs needn't see.

Project namespaces belong to their projects and are not maintained here.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE
from pyspark.sql import SparkSession

from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)

CATALOG = "iceberg"

# Keep in step with teehr-cloud-core control-plane/src/tables.py LAYOUT_DEFAULTS.
LAYOUT_DEFAULTS = {
    "write.target-file-size-bytes": str(64 * 1024**2),
    "write.parquet.row-group-size-bytes": str(8 * 1024**2),
    "write.parquet.row-group-limit": "150000",
}

SNAPSHOT_RETENTION_DAYS = 7
NUM_SNAPSHOTS_TO_KEEP = 10
ORPHAN_FILE_RETENTION_DAYS = 3


def _ts(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S")


def _month_start(months_since_epoch: int) -> datetime:
    year, month = divmod(months_since_epoch, 12)
    return datetime(1970 + year, month + 1, 1, tzinfo=UTC)


def partition_range(field: str, value: int) -> str | None:
    """A filter for one partition of a month- or year-partitioned table (Iceberg
    names those fields ``<column>_month`` / ``<column>_year``); None for others."""
    column, _, transform = field.rpartition("_")
    if transform == "month":
        start, end = _month_start(value), _month_start(value + 1)
    elif transform == "year":
        start, end = _month_start(value * 12), _month_start((value + 1) * 12)
    else:
        return None
    return f"{column} >= TIMESTAMP '{_ts(start)}' AND {column} < TIMESTAMP '{_ts(end)}'"


@task(task_run_name="layout-properties-{table}", cache_policy=NO_CACHE)
def set_layout_properties(spark: SparkSession, namespace: str, table: str) -> list[str]:
    """Give the table the layout defaults it lacks; returns the keys set."""
    have = {
        r["key"]: r["value"]
        for r in spark.sql(f"SHOW TBLPROPERTIES {CATALOG}.{namespace}.{table}").collect()
    }
    missing = {k: v for k, v in LAYOUT_DEFAULTS.items() if k not in have}
    if missing:
        pairs = ", ".join(f"'{k}' = '{v}'" for k, v in missing.items())
        spark.sql(f"ALTER TABLE {CATALOG}.{namespace}.{table} SET TBLPROPERTIES ({pairs})")
    return sorted(missing)


def changed_partitions(
    spark: SparkSession, namespace: str, table: str, since: datetime | None
) -> list[str | None]:
    """Filters for the table's partitions changed since ``since`` (all when None).
    ``[None]`` for an unpartitioned table (rewritten whole); ``[]`` if none changed."""
    # Unpartitioned tables' partitions table has no `partition` column (one row).
    rows = [
        r.asDict()
        for r in spark.sql(f"SELECT * FROM {CATALOG}.{namespace}.{table}.partitions").collect()
    ]
    out: list[str | None] = []
    for row in rows:
        updated = row.get("last_updated_at")
        if (
            since is not None
            and updated is not None
            and updated.replace(tzinfo=updated.tzinfo or UTC) < since
        ):
            continue
        partition = row.get("partition")
        fields = partition.asDict() if partition else {}
        where = (
            partition_range(*next(iter(fields.items())))
            if len(fields) == 1 and next(iter(fields.values())) is not None
            else None
        )
        if where is None:
            return [None]  # unpartitioned, or not by one time field: the whole table
        out.append(where)
    return out


@task(
    task_run_name="sorted-rewrite-{table}",
    timeout_seconds=4 * 60 * 60,
    retries=1,
    retry_delay_seconds=60,
    cache_policy=NO_CACHE,
)
def sorted_rewrite(
    spark: SparkSession,
    namespace: str,
    table: str,
    where: str | None,
    concurrent: int,
) -> None:
    """Rewrite the rows ``where`` keeps (all when None) in the table's sort order,
    at its target file and row-group sizes. One call for every partition: Spark
    rewrites ``concurrent`` file groups (about a partition each) at once."""
    logger = get_run_logger()
    where_arg = f', where => "{where}"' if where else ""
    result = spark.sql(f"""
        CALL {CATALOG}.system.rewrite_data_files(
            table => '{namespace}.{table}',
            strategy => 'sort'{where_arg},
            options => map(
                'rewrite-all', 'true',
                'partial-progress.enabled', 'true',
                'max-concurrent-file-group-rewrites', '{concurrent}'
            )
        )
    """).collect()
    logger.info(f"{table}: {result[0].asDict() if result else {}}")


@task(task_run_name="tidy-{table}", timeout_seconds=30 * 60, cache_policy=NO_CACHE)
def tidy(spark: SparkSession, namespace: str, table: str) -> None:
    """Expire old snapshots, remove orphan files, rewrite manifests."""
    now = datetime.now(UTC)
    name = f"{namespace}.{table}"
    spark.sql(f"""
        CALL {CATALOG}.system.expire_snapshots(
            table => '{name}',
            older_than => TIMESTAMP '{_ts(now - timedelta(days=SNAPSHOT_RETENTION_DAYS))}',
            retain_last => {NUM_SNAPSHOTS_TO_KEEP}
        )
    """).collect()
    spark.sql(f"""
        CALL {CATALOG}.system.remove_orphan_files(
            table => '{name}',
            older_than => TIMESTAMP '{_ts(now - timedelta(days=ORPHAN_FILE_RETENTION_DAYS))}'
        )
    """).collect()
    spark.sql(f"CALL {CATALOG}.system.rewrite_manifests(table => '{name}')").collect()


@flow(
    flow_run_name="v1-table-maintenance",
    timeout_seconds=6 * 60 * 60,
)
def v1_table_maintenance(
    temp_dir_path: str | Path,
    namespace: str = "public",
    tables: list[str] | None = None,
    days: int | None = 8,
    rewrite: bool = True,
    concurrent_rewrites: int = 16,
    start_spark_cluster: bool = True,
    executor_instances: int = 8,
    executor_cores: int = 4,
    executor_memory: str = "16g",
) -> None:
    """Lay out and tidy the v1 tables in ``namespace``: ``tables`` (default all).

    ``days``: rewrite partitions changed in that many days (None: every partition,
    e.g. after the layout defaults change). ``rewrite=False`` only sets properties
    and tidies. ``concurrent_rewrites``: file groups (about a partition each) Spark
    rewrites at once.
    """
    logger = get_run_logger()
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
        update_configs={
            "spark.sql.session.timeZone": "UTC",
            # Orphan-file removal lists the table's files through Hadoop, which needs
            # a FileSystem for s3:// (as routine-table-maintenance sets).
            "spark.hadoop.fs.s3.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
            "spark.hadoop.fs.AbstractFileSystem.s3.impl": "org.apache.hadoop.fs.s3a.S3A",
        },
    )
    spark = ev.spark
    names = tables or sorted(
        r["tableName"] for r in spark.sql(f"SHOW TABLES IN {CATALOG}.{namespace}").collect()
    )
    since = None if days is None else datetime.now(UTC) - timedelta(days=days)
    for table in names:
        set_now = set_layout_properties(spark, namespace, table)
        if set_now:
            logger.info(f"{table}: set {', '.join(set_now)}")
        if rewrite:
            # New layout properties apply to every partition, not just changed ones.
            every = bool(set_now) or since is None
            parts = changed_partitions(spark, namespace, table, None if every else since)
            logger.info(f"{table}: {len(parts)} partition(s) to rewrite")
            if parts:
                where = (
                    None if every or None in parts
                    else " OR ".join(f"({w})" for w in parts)
                )  # fmt: skip
                sorted_rewrite(spark, namespace, table, where, concurrent_rewrites)
        tidy(spark, namespace, table)
    logger.info(f"Maintained {len(names)} table(s) in {namespace}")
