"""
Reference data collection endpoints (configurations, units, variables).

These are lookup/domain tables used to validate and describe timeseries data.
"""

import time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..database import execute_query, sanitize_string, trino_catalog, trino_schema

router = APIRouter()


@router.get("/collections/configurations/items")
async def get_configuration_items(
    request: Request,
    name: str | None = Query(None, description="Filter by configuration name"),
    type: str | None = Query(None, description="Filter by type (primary, secondary)"),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get configuration definitions.

    Configurations describe data sources (e.g., 'nwm30_retrospective',
    'usgs_observations') with their type (primary or secondary) and description.
    """
    try:
        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        if type:
            safe_type = sanitize_string(type)
            where_conditions.append(f"type = '{safe_type}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT
                name,
                type,
                description
            FROM {trino_catalog}.{trino_schema}.configurations
            WHERE {where_clause}
            ORDER BY name
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Configurations query execution time: {query_time:.3f} seconds")

        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/configurations",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configurations: {str(e)}",
        ) from e


@router.get("/collections/units/items")
async def get_unit_items(
    request: Request,
    name: str | None = Query(None, description="Filter by unit name"),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get unit definitions.

    Units describe measurement units (e.g., 'm^3/s', 'ft^3/s') with optional
    conversion factors or descriptions.
    """
    try:
        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.units
            WHERE {where_clause}
            ORDER BY name
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Units query execution time: {query_time:.3f} seconds")

        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/units",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load units: {str(e)}",
        ) from e


@router.get("/collections/variables/items")
async def get_variable_items(
    request: Request,
    name: str | None = Query(None, description="Filter by variable name"),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get variable definitions.

    Variables describe measured quantities (e.g., 'streamflow_hourly_inst')
    with their descriptions.
    """
    try:
        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.variables
            WHERE {where_clause}
            ORDER BY name
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Variables query execution time: {query_time:.3f} seconds")

        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/variables",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load variables: {str(e)}",
        ) from e


@router.get("/collections/attributes/items")
async def get_attribute_items(
    request: Request,
    name: str | None = Query(None, description="Filter by attribute name"),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get attribute definitions.

    Attributes define the available location attribute types (e.g., 'drainage_area_km2',
    'state', 'huc8') with their descriptions.
    """
    try:
        where_conditions = []

        if name:
            safe_name = sanitize_string(name)
            where_conditions.append(f"name = '{safe_name}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.attributes
            WHERE {where_clause}
            ORDER BY name
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Attributes query execution time: {query_time:.3f} seconds")

        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/attributes",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        return JSONResponse(content=response, media_type="application/json")

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load attributes: {str(e)}",
        ) from e


@router.get("/collections/location_attributes/items")
async def get_location_attribute_items(
    request: Request,
    location_id: list[str] | None = Query(
        None, description="Filter by location ID(s) - can be specified multiple times"
    ),
    prefix: str | None = Query(
        None, description="Filter by location ID prefix (e.g., 'usgs', 'nwm')"
    ),
    attribute_name: str | None = Query(None, description="Filter by attribute name"),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get location attribute values.

    Returns the attribute values associated with locations. Each row is a
    location_id + attribute_name + value triple.

    Use this endpoint to:
    - Get all attributes for a specific location
    - Get all attributes for multiple locations (repeat location_id parameter)
    - Get all attributes for locations with a specific prefix (e.g., 'usgs')
    - Get a specific attribute across all locations
    - Query attribute values without geometry overhead
    """
    try:
        where_conditions = []

        if location_id:
            # Multiple location IDs - use IN clause
            safe_locations = [f"'{sanitize_string(loc)}'" for loc in location_id]
            where_conditions.append(f"location_id IN ({', '.join(safe_locations)})")

        if prefix:
            safe_prefix = sanitize_string(prefix)
            where_conditions.append(f"location_id LIKE '{safe_prefix}-%'")

        if attribute_name:
            safe_attr = sanitize_string(attribute_name)
            where_conditions.append(f"attribute_name = '{safe_attr}'")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        query = f"""
            SELECT
                location_id,
                attribute_name,
                value
            FROM {trino_catalog}.{trino_schema}.location_attributes
            WHERE {where_clause}
            ORDER BY location_id, attribute_name
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Location attributes query execution time: {query_time:.3f} seconds")

        items = df.to_dict(orient="records") if not df.empty else []

        response = {
            "items": items,
            "numberReturned": len(items),
            "links": [
                {"href": str(request.url), "rel": "self", "type": "application/json"},
                {
                    "href": "/collections/location_attributes",
                    "rel": "collection",
                    "type": "application/json",
                },
            ],
        }

        # Add pagination links
        if len(items) == limit:
            from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

            parsed = urlparse(str(request.url))
            query_params = parse_qs(parsed.query)
            query_params["offset"] = [str(offset + limit)]
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
            detail=f"Failed to load location attributes: {str(e)}",
        ) from e
