from pathlib import Path
from typing import Union
import logging
from datetime import timedelta, datetime

from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from pyspark.sql import SparkSession

from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)

ORPHAN_FILE_RETENTION_DAYS = 2
SNAPSHOT_RETENTION_DAYS = 7
NUM_SNAPSHOTS_TO_KEEP = 10

REWRITE_TABLE_SORT_ORDER = {
    "primary_timeseries": "value_time ASC NULLS LAST",
    "secondary_timeseries": "zorder(value_time, reference_time)",
}
REWRITE_TABLE_STRATEGY = "sort"  # Can be 'sort' or 'binpack'


@task(
    task_run_name="expire-snapshots-{table_name}",
    timeout_seconds=10 * 60,
    retries=2,
    retry_delay_seconds=30,
    cache_policy=NO_CACHE
)
def expire_snapshots(
    spark: SparkSession,
    table_name: str,
    expiry_date: str,
    num_snapshots_to_keep: int
) -> None:
    """Expire old snapshots to remove unreferenced data files."""
    logger = get_run_logger()
    logger.info(f"Expiring snapshots on {table_name}")
    query = f"""
        CALL iceberg.system.expire_snapshots(
            table => 'teehr.{table_name}',
            older_than => TIMESTAMP '{expiry_date}',
            retain_last => {num_snapshots_to_keep}
    );"""
    spark.sql(query).show()


@task(
    task_run_name="remove-orphan-files-{table_name}",
    timeout_seconds=10 * 60,
    retries=2,
    retry_delay_seconds=30,
    cache_policy=NO_CACHE
)
def remove_orphan_files(
    spark: SparkSession,
    table_name: str,
    expiry_date: str
) -> None:
    """Remove orphan files left over from failed jobs or expired snapshots."""
    logger = get_run_logger()
    logger.info(f"Removing orphan files on {table_name}")
    query = f"""
        CALL iceberg.system.remove_orphan_files(
            table => 'teehr.{table_name}',
            older_than => TIMESTAMP '{expiry_date}'
    );"""
    spark.sql(query).show()


@task(
    task_run_name="rewrite-data-files-{table_name}",
    timeout_seconds=45 * 60,
    retries=1,
    retry_delay_seconds=60,
    cache_policy=NO_CACHE
)
def rewrite_data_files(
    spark: SparkSession,
    table_name: str,
    sort_order: str,
    strategy: str,
) -> None:
    """Compact small data files and apply z-order sorting."""
    logger = get_run_logger()
    logger.info(f"Rewriting data files on {table_name}")
    if strategy == "sort":
        logger.info(f"Using sort strategy with sort order: {sort_order}")
        query = f"""
            CALL iceberg.system.rewrite_data_files(
                table => 'teehr.{table_name}',
                strategy => '{strategy}',
                sort_order => '{sort_order}',
                options => map('target-file-size-bytes', '536870912') -- 512 MB
        );"""
    elif strategy == "binpack":
        logger.info(f"Using binpack strategy for {table_name}")
        query = f"""
            CALL iceberg.system.rewrite_data_files(
                table => 'teehr.{table_name}',
                strategy => '{strategy}',
                options => map('target-file-size-bytes', '536870912') -- 512 MB
        );"""
    else:
        logger.warning(f"Unknown rewrite strategy {strategy} for {table_name}. Skipping rewrite.")
        return
    spark.sql(query).show()


@task(
    task_run_name="rewrite-manifests-{table_name}",
    timeout_seconds=10 * 60,
    retries=2,
    retry_delay_seconds=30,
    cache_policy=NO_CACHE
)
def rewrite_manifests(
    spark: SparkSession,
    table_name: str
) -> None:
    """Merge small manifest files to speed up query planning."""
    logger = get_run_logger()
    logger.info(f"Rewriting manifests on {table_name}")
    query = f"""
        CALL iceberg.system.rewrite_manifests(
            'teehr.{table_name}'
    );"""
    spark.sql(query).show()


@flow(
    flow_run_name="routine-table-maintenance",
    timeout_seconds=3 * 60 * 60,  # 3 hours
)
def routine_table_maintenance(
    dir_path: Union[str, Path]
) -> None:
    """Routine table maintenance workflow.

    1. expire_snapshots - Delete unreferenced files first so subsequent steps skip stale data.
    2. remove_orphan_files - Cleans up left over files from failed jobs or expired snapshots.
    3. rewrite_data_files - Consolidates small files with zorder for better read performance.
    4. rewrite_manifests - Merges small manifest files to speed up query planning.
    """
    logger = get_run_logger()

    logger.info("Starting routine table maintenance...")

    snapshot_expiry_date = (
        datetime.now() - timedelta(days=SNAPSHOT_RETENTION_DAYS)
    ).strftime("%Y-%m-%d %H:%M:%S.000")
    orphan_file_expiry_date = (
        datetime.now() - timedelta(days=ORPHAN_FILE_RETENTION_DAYS)
    ).strftime("%Y-%m-%d %H:%M:%S.000")

    ev = initialize_evaluation(
        dir_path=dir_path,
        start_spark_cluster=True,
        executor_instances=20,
        executor_cores=3,
        executor_memory="16g",
        update_configs={
            "spark.hadoop.fs.s3.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
            "spark.hadoop.fs.AbstractFileSystem.s3.impl": "org.apache.hadoop.fs.s3a.S3A"
        }
    )
    table_names = ev.list_tables()["name"].tolist()

    for table_name in table_names:
        logger.info(f"Performing maintenance on table: {table_name}")
        expire_snapshots(
            spark=ev.spark,
            table_name=table_name,
            expiry_date=snapshot_expiry_date,
            num_snapshots_to_keep=NUM_SNAPSHOTS_TO_KEEP
        )
        remove_orphan_files(
            spark=ev.spark,
            table_name=table_name,
            expiry_date=orphan_file_expiry_date
        )
        if table_name in REWRITE_TABLE_SORT_ORDER:
            rewrite_data_files(
                spark=ev.spark,
                table_name=table_name,
                sort_order=REWRITE_TABLE_SORT_ORDER[table_name],
                strategy=REWRITE_TABLE_STRATEGY
            )
        rewrite_manifests(
            spark=ev.spark,
            table_name=table_name
        )
        logger.info(f"Completed maintenance on table: {table_name}")