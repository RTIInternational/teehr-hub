"""Debug flow that sleeps to allow shelling into the pod."""
import time
from prefect import flow, get_run_logger
from typing import Union
from pathlib import Path

from workflows.utils.common_utils import initialize_evaluation


@flow
def debug_sleep(dir_path: Union[str, Path], sleep_seconds: int = 1800):
    """Sleep to keep the pod alive for debugging."""
    logger = get_run_logger()
    ev = initialize_evaluation(
        dir_path,
        executor_instances=2
    )
    logger.info(f"Debug pod running. Sleeping for {sleep_seconds}s...")
    time.sleep(sleep_seconds)
    logger.info("Debug sleep complete.")
    ev.spark.stop()
