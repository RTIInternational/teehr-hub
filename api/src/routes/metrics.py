"""
Metrics collection endpoints (OGC API Features).
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from ..auth import effective_limit_for_request
from ..database import (
    execute_query, sanitize_string, trino_catalog, trino_schema
)
from .queryables import get_metrics_table_queryables
from .utils import create_ogc_geojson_response, prepare_for_serialization

router = APIRouter()
logger = logging.getLogger("teehr-api.routes.metrics")

def _verify_filtered_columns(
        table: str,
        filtered_columns: list[str]
):
    """Validate filtered columns against group-by columns for collection.

    Respond with 400 if invalid filters found.
    """
    queryables = get_metrics_table_queryables(table)
    available_columns = queryables["x-teehr-group-by"]
    invalid_filters = set(filtered_columns) - set(available_columns)
    if invalid_filters:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported filters: {', '.join(sorted(invalid_filters))}"
        )

@router.get("/collections/{collection_id}/items")
async def get_collection_items(
    collection_id: str,
    request: Request,
    location_id: str | None = Query(
        None, alias="location_id", description="Filter by location ID"
    ),
    configuration_name: str | None = Query(
        None, description="Filter by configuration name"
    ),
    variable_name: str | None = Query(
        None,
        description="Filter by variable name"
    ),
    limit: int | None = Query(
        None, ge=1, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None,
        ge=0,
        description="Starting index for pagination"
    ),
):
    """Get items from any collection (OGC API Features endpoint).

    Handles metrics tables. The locations collection has its own endpoint.

    Dynamic filtering is supported through the inclusion of additional query parameters.
    All additional query parameters will be interpreted as equality filters against
    collection columns.

    If an invalid filter is requested, endpoint will respond with HTTP 400.
    """
    try:
        RESERVED_PARAMS = ["collection_id", "location_id", "limit", "offset"]

        limit = effective_limit_for_request(request, limit)

        # Use the collection_id as the table name
        sanitized_table = sanitize_string(collection_id)

        filters = {
            k: v
            for k, v in request.query_params.items()
            if k not in RESERVED_PARAMS
        }

        _verify_filtered_columns(sanitized_table, filters.keys())

        if "location_id" in request.query_params:
            sanitized_location_id = sanitize_string(request.query_params["location_id"])
            where_conditions = [
                f"primary_location_id = '{sanitized_location_id}'"
            ]
        else:
            where_conditions = ["primary_location_id LIKE 'usgs-%'"]

        for column, value in filters.items():
            sanitized_column = sanitize_string(column)
            sanitized_value = sanitize_string(value)
            where_conditions.append(f"{sanitized_column} = '{sanitized_value}'")

        where_clause = " AND ".join(where_conditions)

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

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        logger.debug("Metrics query execution time: %.3f seconds", query_time)

        df = prepare_for_serialization(df)
        geojson = create_ogc_geojson_response(
            df,
            str(request.url),
            collection_id=collection_id,
            limit=limit,
            offset=offset,
        )

        return JSONResponse(
            content=geojson,
            headers={
                "Content-Type": "application/geo+json",
                "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",  # noqa: E501
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load collection '{collection_id}': {str(e)}",
        ) from e
