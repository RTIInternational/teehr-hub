from pathlib import Path
from typing import Union
import logging

from prefect import flow, get_run_logger

from utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)


@flow(
    flow_run_name="update-joined-timeseries-table",
    timeout_seconds=60 * 60,
    retries=2
)
def update_joined_timeseries_table(
    dir_path: Union[str, Path]
) -> None:
    """Create the joined timeseries table

    Notes
    -----
    - Ultimately the join will be updated to include a filter so
      so that recent data can be joined and appended to the existing table.
    - Currently, the entire joined table is re-created each time.
    """
    logger = get_run_logger()

    ev = initialize_evaluation(dir_path=dir_path)

    logger.info("Creating joined timeseries table...")
    ev.joined_timeseries.create(
        write_mode="create_or_replace"
    )
    logger.info("Joined timeseries table created.")
