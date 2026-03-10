"""
Database utilities for updating analytics run status.

Uses Trino to update the analytics_runs table in the teehr_results schema.
"""

import logging
import os
from datetime import datetime
from enum import Enum
from typing import Optional

import trino

logger = logging.getLogger(__name__)


class RunStatus(str, Enum):
    """Run status values."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# Trino connection config
TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
TRINO_USER = os.environ.get("TRINO_USER", "teehr")
TRINO_CATALOG = os.environ.get("TRINO_CATALOG", "iceberg")
RESULT_SCHEMA = "teehr_results"


def _get_connection():
    """Get Trino connection."""
    return trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user=TRINO_USER,
        catalog=TRINO_CATALOG,
        schema=RESULT_SCHEMA,
    )


def _execute_update(query: str) -> None:
    """Execute an update query."""
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        # Trino requires fetching results even for updates
        cursor.fetchall()
    finally:
        conn.close()


def update_run_status(
    run_id: str,
    status: RunStatus,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
    result_table: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """Update the status of an analytics run.

    Parameters
    ----------
    run_id : str
        The run identifier.
    status : RunStatus
        New status value.
    started_at : datetime, optional
        When the run started.
    finished_at : datetime, optional
        When the run finished.
    result_table : str, optional
        Name of result table (on success).
    error_message : str, optional
        Error message (on failure).
    """
    # Build SET clause
    set_parts = [f"status = '{status.value}'"]

    if started_at:
        set_parts.append(f"started_at = TIMESTAMP '{started_at.isoformat()}'")

    if finished_at:
        set_parts.append(f"finished_at = TIMESTAMP '{finished_at.isoformat()}'")

    if result_table:
        set_parts.append(f"result_table = '{result_table}'")

    if error_message:
        # Escape single quotes in error message
        escaped_msg = error_message.replace("'", "''")
        set_parts.append(f"error_message = '{escaped_msg}'")

    set_clause = ", ".join(set_parts)

    query = f"""
        UPDATE {TRINO_CATALOG}.{RESULT_SCHEMA}.analytics_runs
        SET {set_clause}
        WHERE run_id = '{run_id}'
    """

    try:
        _execute_update(query)
        logger.info(f"Updated run {run_id} status to {status.value}")
    except Exception as e:
        logger.error(f"Failed to update run {run_id} status: {e}")
        # Don't raise - we want the job to continue even if status update fails
