"""
FIRO dashboard-specific API endpoints.

These endpoints serve data from FIRO custom tables (locations_metrics,
event_rankings, event_heatmap, joined_timeseries) that were loaded via
ev._load.dataframe() and therefore:
  - Have no geometry column (cannot use the shared OGC GeoJSON pathway).
  - Have no Iceberg table properties (group_by / metrics) set, so the shared
    _verify_filtered_columns guard in metrics.py rejects column filters.

All endpoints return plain JSON arrays of row objects rather than GeoJSON so
that the frontend can consume them without geometry processing overhead.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..auth import effective_limit_for_request
from ..database import (
    execute_query,
    sanitize_string,
    trino_catalog,
    trino_schema,
)
from .utils import prepare_for_serialization

router = APIRouter(prefix="/firo", tags=["FIRO"])
logger = logging.getLogger("teehr-api.routes.firo")

# Tables that are served by this router.
FIRO_TABLES = {
    "locations_metrics",
    "event_rankings",
    "event_heatmap",
    "joined_timeseries",
}

# Columns that the frontend may filter on for each table.
# Only columns that are genuine filter dimensions (not metrics) should be here.
ALLOWED_FILTERS: dict[str, set[str]] = {
    "locations_metrics": {
        "primary_location_id",
        "configuration_name",
        "variable_name",
        "season",
        "forecast_lead_time_bin",
        "threshold",
    },
    "event_rankings": {
        "primary_location_id",
        "configuration_name",
        "variable_name",
        "threshold",
    },
    "event_heatmap": {
        "primary_location_id",
        "configuration_name",
        "variable_name",
        "event_id",
        "threshold",
    },
    "joined_timeseries": {
        "primary_location_id",
        "configuration_name",
        "variable_name",
        "reference_time",
        "member",
    },
}


def _build_where_clause(
    table: str,
    location_id: str | None,
    extra_filters: dict[str, str],
) -> str:
    """Build a WHERE clause from validated filters.

    ``location_id`` is handled as the primary_location_id equality filter.
    ``extra_filters`` come from query params and are validated against the
    per-table allow-list before being included.
    """
    allowed = ALLOWED_FILTERS.get(table, set())
    conditions: list[str] = []

    if location_id:
        conditions.append(
            f"primary_location_id = '{sanitize_string(location_id)}'"
        )

    for col, val in extra_filters.items():
        if col not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported filter '{col}' for table '{table}'.",
            )
        sanitized_col = sanitize_string(col)
        if val.lower() == "null":
            conditions.append(f"{sanitized_col} IS NULL")
        else:
            conditions.append(f"{sanitized_col} = '{sanitize_string(val)}'")

    return " AND ".join(conditions) if conditions else "1=1"


@router.get("/collections/{table_name}/items")
async def get_firo_table_items(
    table_name: str,
    request: Request,
    location_id: str | None = Query(
        None, alias="location_id", description="Filter by primary_location_id"
    ),
    limit: int | None = Query(
        None, ge=1, description="Maximum rows to return (omit for all)"
    ),
    offset: int | None = Query(None, ge=0, description="Pagination offset"),
):
    """Return rows from a FIRO custom table as a plain JSON array.

    Unlike the shared /collections/{id}/items endpoint, this route handles
    tables that have no geometry column and no Iceberg table properties.
    Accepted tables: locations_metrics, event_rankings, event_heatmap,
    joined_timeseries.

    Any query parameter not in [location_id, limit, offset] is treated as an
    equality filter against the corresponding table column, validated against a
    per-table allow-list.
    """
    if table_name not in FIRO_TABLES:
        raise HTTPException(
            status_code=404,
            detail=(
                f"'{table_name}' is not a FIRO table. "
                f"Use /collections/{{id}}/items for standard collections."
            ),
        )

    sanitized_table = sanitize_string(table_name)

    RESERVED = {"location_id", "limit", "offset"}
    extra_filters = {
        k: v
        for k, v in request.query_params.items()
        if k not in RESERVED
    }

    limit = effective_limit_for_request(request, limit)

    try:
        where_clause = _build_where_clause(sanitized_table, location_id, extra_filters)

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.{sanitized_table}
            WHERE {where_clause}
            ORDER BY primary_location_id
            {pagination}
        """

        df = execute_query(query)

        # Convert ALL datetime-typed columns to strings so they are JSON
        # serialisable.  prepare_for_serialization only handles created_at /
        # updated_at by default; FIRO tables have additional timestamp columns
        # (e.g. reference_time, value_time in joined_timeseries).
        datetime_cols = df.select_dtypes(
            include=["datetime64", "datetimetz"]
        ).columns.tolist()
        df = prepare_for_serialization(df, datetime_columns=datetime_cols or None)

        rows = df.to_dict(orient="records")
        return JSONResponse(
            content={
                "table": table_name,
                "numberReturned": len(rows),
                "items": rows,
            },
            media_type="application/json",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("FIRO table query failed for %s", table_name)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load FIRO table '{table_name}': {exc}",
        ) from exc
