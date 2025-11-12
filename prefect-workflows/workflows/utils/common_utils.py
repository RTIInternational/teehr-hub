from typing import Union
from pathlib import Path

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session

from prefect import task, get_run_logger


@task()
def initialize_evaluation(dir_path: Union[str, Path]) -> teehr.Evaluation:
    """Initialize a Teehr Evaluation object."""
    logger = get_run_logger()
    logger.info("Initializing Teehr Evaluation")
    spark = create_spark_session()
    ev = teehr.Evaluation(
        spark=spark,
        dir_path=dir_path,
        check_evaluation_version=False
    )
    ev.set_active_catalog("remote")
    return ev
