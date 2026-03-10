"""
Analytics endpoints for async Spark-based analytics jobs.

Endpoints:
- POST /analytics/{analytics_id}/runs  - Submit a new analytics run
- GET  /analytics/runs/{run_id}        - Get run status
- GET  /analytics/runs/{run_id}/results - Get run results (paginated)
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.analytics import (
    AnalyticsRunRequest,
    AnalyticsRunResponse,
    AnalyticsRunStatusResponse,
    AnalyticsResultsResponse,
    RunStatusEnum,
)
from ..database import execute_query, trino_catalog

logger = logging.getLogger(__name__)

router = APIRouter()

# Result schema for analytics outputs
RESULT_SCHEMA = "teehr_results"

# Supported analytics types
SUPPORTED_ANALYTICS = {
    "custom_metrics": {
        "description": "Custom metric query with user-defined filters, group_by, and metrics",
        "version": "1",
    }
}


def _get_run_from_db(run_id: str) -> Optional[dict]:
    """Fetch run record from analytics_runs table."""
    query = f"""
        SELECT
            run_id,
            analytics_id,
            cache_key,
            status,
            parameters_json,
            result_table,
            created_at,
            started_at,
            finished_at,
            error_message
        FROM {trino_catalog}.{RESULT_SCHEMA}.analytics_runs
        WHERE run_id = '{run_id}'
    """
    try:
        df = execute_query(query, max_rows=1)
        if df.empty:
            return None
        row = df.iloc[0].to_dict()
        return row
    except Exception as e:
        logger.warning(f"Error fetching run {run_id}: {e}")
        return None


def _find_cached_run(analytics_id: str, cache_key: str) -> Optional[dict]:
    """Find a succeeded run with the same cache key."""
    query = f"""
        SELECT
            run_id,
            analytics_id,
            cache_key,
            status,
            result_table,
            created_at,
            finished_at
        FROM {trino_catalog}.{RESULT_SCHEMA}.analytics_runs
        WHERE analytics_id = '{analytics_id}'
          AND cache_key = '{cache_key}'
          AND status = 'succeeded'
        ORDER BY finished_at DESC
        LIMIT 1
    """
    try:
        df = execute_query(query, max_rows=1)
        if df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception as e:
        logger.warning(f"Error checking cache: {e}")
        return None


def _insert_run_record(
    run_id: str,
    analytics_id: str,
    cache_key: str,
    parameters_json: str,
) -> None:
    """Insert a new run record into analytics_runs table."""
    now = datetime.now(timezone.utc).isoformat()
    query = f"""
        INSERT INTO {trino_catalog}.{RESULT_SCHEMA}.analytics_runs (
            run_id,
            analytics_id,
            cache_key,
            status,
            parameters_json,
            created_at
        ) VALUES (
            '{run_id}',
            '{analytics_id}',
            '{cache_key}',
            'queued',
            '{parameters_json}',
            TIMESTAMP '{now}'
        )
    """
    try:
        execute_query(query)
    except Exception as e:
        logger.error(f"Error inserting run record: {e}")
        raise


@router.post("/{analytics_id}/runs", response_model=AnalyticsRunResponse)
async def create_analytics_run(
    analytics_id: str,
    request: AnalyticsRunRequest,
):
    """Submit a new analytics run.

    The analytics job will run asynchronously on Spark/Kubernetes.
    Returns immediately with a run_id for status polling.

    Caching: If an identical request (same cache_key) has already succeeded,
    returns the cached run instead of submitting a new job.
    """
    # Validate analytics_id
    if analytics_id not in SUPPORTED_ANALYTICS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown analytics_id: {analytics_id}. "
                   f"Supported: {list(SUPPORTED_ANALYTICS.keys())}"
        )

    analytics_config = SUPPORTED_ANALYTICS[analytics_id]
    version = analytics_config["version"]

    # Compute cache key
    cache_key = request.compute_cache_key(analytics_id, version)

    # Check for cached result
    cached_run = _find_cached_run(analytics_id, cache_key)
    if cached_run:
        logger.info(f"Returning cached run {cached_run['run_id']} for cache_key {cache_key}")
        return AnalyticsRunResponse(
            run_id=cached_run["run_id"],
            analytics_id=analytics_id,
            status=RunStatusEnum.succeeded,
            cache_key=cache_key,
            cached=True,
            created_at=cached_run["created_at"],
            result_table=cached_run.get("result_table"),
        )

    # Generate new run_id
    run_id = str(uuid.uuid4())

    # Serialize request for storage
    parameters_json = request.model_dump_json()

    # Insert run record
    try:
        _insert_run_record(run_id, analytics_id, cache_key, parameters_json)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create run record: {e}"
        )

    # Submit Kubernetes Job
    try:
        from ..k8s.jobs import create_analytics_job
        job_name = create_analytics_job(
            run_id=run_id,
            analytics_id=analytics_id,
            parameters_json=parameters_json,
        )
        logger.info(f"Created analytics run {run_id} with job {job_name}")
    except Exception as e:
        logger.error(f"Failed to submit K8s job for run {run_id}: {e}")
        # Don't fail the request - the run record was created
        # Status will remain "queued" and user can retry
        logger.info(f"Created analytics run {run_id} (job submission failed, can be retried)")

    return AnalyticsRunResponse(
        run_id=run_id,
        analytics_id=analytics_id,
        status=RunStatusEnum.queued,
        cache_key=cache_key,
        cached=False,
        created_at=datetime.now(timezone.utc),
        result_table=None,
    )


@router.get("/runs/{run_id}", response_model=AnalyticsRunStatusResponse)
async def get_analytics_run_status(run_id: str):
    """Get the status of an analytics run.

    Checks both the analytics_runs tracking table and the Kubernetes Job status.
    """
    run = _get_run_from_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Check K8s Job status and sync if needed
    job_name = None
    db_status = RunStatusEnum(run["status"])

    if db_status in (RunStatusEnum.queued, RunStatusEnum.running):
        try:
            from ..k8s.jobs import get_job_status
            k8s_status = get_job_status(run_id)
            if k8s_status["exists"]:
                job_name = k8s_status["job_name"]
                # TODO: Optionally sync K8s status back to DB
        except Exception as e:
            logger.warning(f"Failed to get K8s job status for run {run_id}: {e}")

    return AnalyticsRunStatusResponse(
        run_id=run["run_id"],
        analytics_id=run["analytics_id"],
        status=RunStatusEnum(run["status"]),
        cache_key=run["cache_key"],
        created_at=run["created_at"],
        started_at=run.get("started_at"),
        finished_at=run.get("finished_at"),
        result_table=run.get("result_table"),
        error_message=run.get("error_message"),
        job_name=job_name,
    )


@router.get("/runs/{run_id}/results", response_model=AnalyticsResultsResponse)
async def get_analytics_run_results(
    run_id: str,
    limit: int = Query(default=1000, ge=1, le=10000, description="Max rows to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """Get results of a completed analytics run.

    Results are paginated. Only available when run status is 'succeeded'.
    """
    run = _get_run_from_db(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    status = RunStatusEnum(run["status"])

    if status != RunStatusEnum.succeeded:
        return AnalyticsResultsResponse(
            run_id=run_id,
            analytics_id=run["analytics_id"],
            status=status,
            total_rows=None,
            offset=offset,
            limit=limit,
            rows=[],
            links=None,
        )

    result_table = run.get("result_table")
    if not result_table:
        raise HTTPException(
            status_code=500,
            detail=f"Run {run_id} succeeded but has no result_table"
        )

    # Query results from Iceberg
    try:
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as cnt
            FROM {trino_catalog}.{RESULT_SCHEMA}.{result_table}
        """
        count_df = execute_query(count_query, max_rows=1)
        total_rows = int(count_df.iloc[0]["cnt"]) if not count_df.empty else 0

        # Get paginated results
        results_query = f"""
            SELECT *
            FROM {trino_catalog}.{RESULT_SCHEMA}.{result_table}
            OFFSET {offset}
            LIMIT {limit}
        """
        results_df = execute_query(results_query, max_rows=limit)
        rows = results_df.to_dict(orient="records")

    except Exception as e:
        logger.error(f"Error fetching results for run {run_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch results: {e}"
        )

    # Build pagination links
    links = {}
    if offset > 0:
        links["prev"] = f"/analytics/runs/{run_id}/results?limit={limit}&offset={max(0, offset - limit)}"
    if offset + limit < total_rows:
        links["next"] = f"/analytics/runs/{run_id}/results?limit={limit}&offset={offset + limit}"

    return AnalyticsResultsResponse(
        run_id=run_id,
        analytics_id=run["analytics_id"],
        status=status,
        total_rows=total_rows,
        offset=offset,
        limit=limit,
        rows=rows,
        links=links if links else None,
    )


@router.get("/", summary="List available analytics")
async def list_analytics():
    """List available analytics types and their descriptions."""
    return {
        "analytics": [
            {
                "id": aid,
                "description": config["description"],
                "version": config["version"],
            }
            for aid, config in SUPPORTED_ANALYTICS.items()
        ]
    }
