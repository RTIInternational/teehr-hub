from typing import Union, Dict
from pathlib import Path

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session

from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE


@task(
    timeout_seconds=60 * 5,
    retries=2
)
def initialize_evaluation(
    dir_path: Union[str, Path],
    start_spark_cluster: bool = False,
    executor_instances: int = 4,
    executor_cores: int = 4,
    executor_memory: str = "4g"
) -> teehr.Evaluation:
    """Initialize a Teehr Evaluation object."""
    logger = get_run_logger()
    logger.info("Initializing Teehr Evaluation")
    spark = create_spark_session(
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )
    ev = teehr.Evaluation(
        spark=spark,
        dir_path=dir_path,
        create_dir=False,
        update_configs={
            "spark.local.dir": "/data/tmp/spark-temp"
        }
    )
    ev.set_active_catalog("remote")
    return ev


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
