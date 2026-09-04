from typing import Union, Dict
from pathlib import Path
import os
import shutil
import time

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session
from teehr.evaluation.evaluation import RemoteReadWriteEvaluation

from prefect import task, get_run_logger, flow
from prefect.cache_policies import NO_CACHE


@task(
    timeout_seconds=60 * 5,
    retries=2
)
def initialize_evaluation(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 4,
    executor_cores: int = 7,
    executor_memory: str = "50g",
    update_configs: Dict[str, str] = None,
    enable_gcs: bool = False,
    gcs_project_id: str = None
) -> teehr.Evaluation:
    """Initialize a Teehr Evaluation object."""
    logger = get_run_logger()
    logger.info("Initializing Teehr Evaluation")

    remote_catalog_uri = os.getenv("REMOTE_CATALOG_REST_URI", "")
    remote_catalog_type = os.getenv("REMOTE_CATALOG_TYPE", "rest")
    remote_warehouse_dir = os.getenv(
        "REMOTE_WAREHOUSE_IDENTIFIER",
        os.getenv("POLARIS_DEFAULT_REALM", "teehr")
    )

    # Ensure Spark executors run as the prefect-job service account. Iceberg
    # warehouse access comes from Polaris-vended credentials rather than the
    # SA's own IAM role, but the SA is still what grants direct (non-catalog)
    # S3 access and keeps executor identity consistent with the driver.
    #
    # client.region must be set explicitly: without it the Iceberg S3 client
    # cannot resolve a region for SigV4 signing of the vended credentials.
    default_configs = {
        "spark.kubernetes.authenticate.executor.serviceAccountName": "prefect-job",
        "spark.kubernetes.executor.podNamePrefix": "prefect-job",
        "spark.sql.catalog.iceberg.token-exchange-enabled": "false",
        "spark.sql.catalog.iceberg.token-refresh-enabled": "true",
        "spark.sql.catalog.iceberg.client.region": os.getenv(
            "AWS_REGION", "us-east-2"
        )
    }
    if update_configs:
        default_configs.update(update_configs)

    spark = create_spark_session(
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
        remote_catalog_uri=remote_catalog_uri,
        remote_catalog_type=remote_catalog_type,
        remote_warehouse_dir=remote_warehouse_dir,
        update_configs=default_configs,
        enable_gcs=enable_gcs,
        gcs_project_id=gcs_project_id
    )
    ev = RemoteReadWriteEvaluation(
        spark=spark,
        temp_dir_path=temp_dir_path,
    )
    return ev


@task(cache_policy=NO_CACHE)
def table_exists(
    ev: teehr.Evaluation,
    table_name: str,
    catalog_name: str = "iceberg",
    namespace_name: str = "teehr"
) -> bool:
    """Check if a table exists in the warehouse."""
    return ev.spark.catalog.tableExists(f"{catalog_name}.{namespace_name}.{table_name}")


@task(cache_policy=NO_CACHE)
def set_table_properties(
    ev: teehr.Evaluation,
    table_name: str,
    properties: Dict[str, str]
) -> None:
    """Set table properties for a given table in the warehouse."""
    logger = get_run_logger()
    logger.info(f"Setting table properties for {table_name}...")
    for key, value in properties.items():
        ev.spark.sql(f"""
        ALTER TABLE iceberg.teehr.{table_name} SET TBLPROPERTIES ('{key}' = '{value}')
        """)
    logger.info(f"Table properties set for {table_name}.")
