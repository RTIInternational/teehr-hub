"""A simple flow that sleeps for testing."""
import logging
import time

from prefect import flow, get_run_logger


logging.getLogger("test").setLevel(logging.INFO)


@flow(flow_run_name="sleep-for-testing")
def sleep_for_testing():
    """A simple flow that sleeps for 10 mins for testing."""

    logger = get_run_logger()
    logger.info("Sleeping for 10 minutes...")
    time.sleep(10 * 60)
    logger.info("Done sleeping.")