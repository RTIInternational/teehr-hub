"""
Location crosswalks collection endpoints.
"""

import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..database import execute_query, sanitize_string, trino_catalog, trino_schema

router = APIRouter()


@router.get("/collections/location_crosswalks/items")
async def get_crosswalk_items(
    request: Request,
    primary_location_id: list[str] | None = Query(
        None, description="Filter by primary location ID (can be specified multiple times)"
    ),
    secondary_location_id: list[str] | None = Query(
        None, description="Filter by secondary location ID (can be specified multiple times)"
    ),
    limit: int | None = Query(
        None, ge=1, le=10000, description="Maximum number of items to return (omit to return all)"
    ),
    offset: int | None = Query(
        None, ge=0, description="Starting index for pagination"
    ),
):
    """Get location crosswalk mappings.

    Returns mappings between primary (e.g., USGS) and secondary (e.g., NWM)
    location identifiers. This is a non-spatial collection (no geometry).
    """
    try:
        where_conditions = []

        if primary_location_id:
            safe_primary_ids = [f"'{sanitize_string(loc_id)}'" for loc_id in primary_location_id]
            where_conditions.append(f"primary_location_id IN ({', '.join(safe_primary_ids)})")

        if secondary_location_id:
            safe_secondary_ids = [f"'{sanitize_string(loc_id)}'" for loc_id in secondary_location_id]
            where_conditions.append(f"secondary_location_id IN ({', '.join(safe_secondary_ids)})")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        pagination = ""
        if offset is not None:
            pagination += f" OFFSET {offset}"
        if limit is not None:
            pagination += f" LIMIT {limit}"

        query = f"""
            SELECT
                primary_location_id,
                secondary_location_id
            FROM {trino_catalog}.{trino_schema}.location_crosswalks
            WHERE {where_clause}
            ORDER BY primary_location_id, secondary_location_id
            {pagination}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Crosswalks query execution time: {query_time:.3f} seconds")

        if df.empty:
            return JSONResponse(
                content={
                    "items": [],
                    "numberReturned": 0,
                    "links": [
                        {
                            "href": str(request.url),
                            "rel": "self",
                            "type": "application/json",
                        }
                    ],
                },
                media_type="application/json",
            )

        items = df.to_dict(orient="records")

        # Build response with OGC-style metadata
        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {
                    "href": str(request.url),
                    "rel": "self",
                    "type": "application/json",
                },
                {
                    "href": "/collections/location_crosswalks",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        # Add pagination links
        if limit is not None and len(items) == limit:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(str(request.url))
            query_params = parse_qs(parsed.query)
            query_params["offset"] = [str((offset or 0) + limit)]
            query_params["limit"] = [str(limit)]
            next_query = urlencode({k: v[0] for k, v in query_params.items()})
            next_url = urlunparse(parsed._replace(query=next_query))
            response["links"].append(
                {"href": next_url, "rel": "next", "type": "application/json"}
            )

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load crosswalks: {str(e)}",
        ) from e
