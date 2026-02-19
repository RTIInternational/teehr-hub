from pathlib import Path
from typing import Union
import logging
from datetime import timedelta, datetime

from prefect import flow, task, get_run_logger
from pyspark.sql import SparkSession

from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)

ORPHAN_FILE_RETENTION_DAYS = 2
SNAPSHOT_RETENTION_DAYS = 7
NUM_SNAPSHOTS_TO_KEEP = 10

REWRITE_TABLE_CONFIGS = {
    "primary_timeseries": "zorder(configuration_name, location_id, value_time)",
    "secondary_timeseries": "zorder(configuration_name, location_id, value_time, reference_time)",
}


@task(
    task_run_name="expire-snapshots-{table_name}",
    timeout_seconds=10 * 60,
    retries=2,
    retry_delay_seconds=30
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
    retry_delay_seconds=30
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
    retry_delay_seconds=60
)
def rewrite_data_files(
    spark: SparkSession,
    table_name: str,
    sort_order: str
) -> None:
    """Compact small data files and apply z-order sorting."""
    logger = get_run_logger()
    logger.info(f"Rewriting data files on {table_name} with {sort_order}")
    query = f"""
        CALL iceberg.system.rewrite_data_files(
            table => 'teehr.{table_name}',
            strategy => 'sort',
            sort_order => '{sort_order}',
            options => map('target-file-size-bytes', '536870912') -- 512 MB
    );"""
    spark.sql(query).show()


@task(
    task_run_name="rewrite-manifests-{table_name}",
    timeout_seconds=10 * 60,
    retries=2,
    retry_delay_seconds=30
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

    expire_snapshots - Delete unreferenced files first so subsequent steps skip stale data.
    remove_orphan_files - Cleans up left over files from failed jobs or expired snapshots.
    rewrite_data_files - Consolidates small files with zorder for better read performance.
    rewrite_manifests - Merges small manifest files to speed up query planning.
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
            "spark.kubernetes.executor.node.selector.teehr-hub/nodegroup-name": "spark-r5-4xlarge-spot",
            "spark.decommission.enabled": "true",
            "spark.executor.decommission.signal": "SIGTERM",
            "spark.storage.decommission.enabled": "true",
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
        if table_name in REWRITE_TABLE_CONFIGS:
            rewrite_data_files(
                spark=ev.spark,
                table_name=table_name,
                sort_order=REWRITE_TABLE_CONFIGS[table_name]
            )
        rewrite_manifests(
            spark=ev.spark,
            table_name=table_name
        )
        logger.info(f"Completed maintenance on table: {table_name}")