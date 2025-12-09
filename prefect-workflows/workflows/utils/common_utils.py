from typing import Union
from pathlib import Path

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session

from prefect import task, get_run_logger


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
        create_dir=False
    )
    ev.set_active_catalog("remote")
    return ev
