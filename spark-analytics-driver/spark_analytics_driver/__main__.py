"""
Main entrypoint for the Spark analytics driver.

This module is executed as: python -m spark_analytics_driver

It reads configuration from environment variables, runs the specified
analytics, and writes results to Iceberg.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone

from teehr.evaluation.spark_session_utils import create_spark_session
from teehr.evaluation.evaluation import RemoteReadWriteEvaluation

from .analytics_registry import ANALYTICS_REGISTRY
from .db import update_run_status, RunStatus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("spark-analytics-driver")
logging.getLogger("teehr").setLevel(logging.INFO)


def main():
    """Main entrypoint for analytics driver."""
    # Read configuration from environment
    run_id = os.environ.get("RUN_ID")
    analytics_id = os.environ.get("ANALYTICS_ID")
    parameters_json = os.environ.get("PARAMETERS_JSON")

    if not all([run_id, analytics_id, parameters_json]):
        logger.error("Missing required environment variables: RUN_ID, ANALYTICS_ID, PARAMETERS_JSON")
        sys.exit(1)

    logger.info(f"Starting analytics run {run_id}")
    logger.info(f"Analytics ID: {analytics_id}")

    # Parse parameters
    try:
        parameters = json.loads(parameters_json)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse PARAMETERS_JSON: {e}")
        update_run_status(run_id, RunStatus.FAILED, error_message=f"Invalid parameters: {e}")
        sys.exit(1)

    # Get analytics handler
    if analytics_id not in ANALYTICS_REGISTRY:
        msg = f"Unknown analytics_id: {analytics_id}"
        logger.error(msg)
        update_run_status(run_id, RunStatus.FAILED, error_message=msg)
        sys.exit(1)

    analytics_class = ANALYTICS_REGISTRY[analytics_id]

    # Update status to running
    update_run_status(run_id, RunStatus.RUNNING, started_at=datetime.now(timezone.utc))

    # Create Spark session with executor SA override for read-write access
    logger.info("Creating Spark session...")
    try:
        spark = create_spark_session(
            start_spark_cluster=True,
            executor_instances=4,
            executor_cores=7,
            executor_memory="50g",
            update_configs={
                # Use prefect-job SA which has read-write IRSA
                "spark.kubernetes.authenticate.executor.serviceAccountName": "prefect-job"
            }
        )
    except Exception as e:
        msg = f"Failed to create Spark session: {e}"
        logger.error(msg)
        update_run_status(run_id, RunStatus.FAILED, error_message=msg)
        sys.exit(1)

    # Create evaluation object
    temp_dir = "/tmp/spark-analytics"
    os.makedirs(temp_dir, exist_ok=True)

    logger.info("Creating RemoteReadWriteEvaluation...")
    ev = RemoteReadWriteEvaluation(spark=spark, temp_dir_path=temp_dir)

    # Run analytics
    try:
        analytics = analytics_class()
        result_table = analytics.run(
            ev=ev,
            run_id=run_id,
            parameters=parameters,
        )

        # Update status to succeeded
        update_run_status(
            run_id,
            RunStatus.SUCCEEDED,
            finished_at=datetime.now(timezone.utc),
            result_table=result_table,
        )
        logger.info(f"Analytics run {run_id} completed successfully. Result table: {result_table}")

    except Exception as e:
        msg = f"Analytics execution failed: {e}"
        logger.exception(msg)
        update_run_status(
            run_id,
            RunStatus.FAILED,
            finished_at=datetime.now(timezone.utc),
            error_message=str(e),
        )
        sys.exit(1)

    finally:
        # Stop Spark session
        try:
            spark.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
