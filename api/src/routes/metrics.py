"""
Metrics collection endpoints (OGC API Features).
"""

import json
import time

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..config import config
from ..database import (
    execute_query, sanitize_string, trino_catalog, trino_schema
)
from .utils import create_ogc_geojson_response

router = APIRouter()


@router.get("/collections/{collection_id}/items")
async def get_collection_items(
    collection_id: str,
    request: Request,
    location_id: str | None = Query(
        None, alias="location_id", description="Filter by location ID"
    ),
    configuration: str | None = Query(
        None, description="Filter by configuration"
    ),
    parameter: str | None = Query(
        None,
        alias="parameter",
        description="Filter by parameter/variable name"
    ),
    bbox: str | None = Query(
        None, description="Bounding box filter (minLon,minLat,maxLon,maxLat)"
    ),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0,
        ge=0,
        description="Starting index for pagination"
    ),
):
    """Get items from any collection (OGC API Features endpoint).

    Handles metrics tables. The locations collection has its own endpoint.
    """
    try:
        # Use the collection_id as the table name
        sanitized_table = sanitize_string(collection_id)

        if location_id:
            sanitized_location_id = sanitize_string(location_id)
            where_conditions = [
                f"primary_location_id = '{sanitized_location_id}'"
            ]
        else:
            where_conditions = ["primary_location_id LIKE 'usgs-%'"]

        if configuration:
            sanitized_configuration = sanitize_string(configuration)
            where_conditions.append(
                f"configuration_name = '{sanitized_configuration}'"
            )
        if parameter:
            sanitized_variable = sanitize_string(parameter)
            where_conditions.append(f"variable_name = '{sanitized_variable}'")

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT *
            FROM {trino_catalog}.{trino_schema}.{sanitized_table}
            WHERE {where_clause}
            ORDER BY primary_location_id
            OFFSET {offset}
            LIMIT {limit}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        if df.empty:
            empty_response = create_ogc_geojson_response(
                {"type": "FeatureCollection", "features": []},
                str(request.url),
                collection_id=collection_id,
            )
            return JSONResponse(
                content=empty_response,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",  # noqa: E501
                },
            )

        # Process geometry in chunks for large datasets
        chunk_size = config.CHUNK_SIZE
        if len(df) > chunk_size:
            print(
                f"Large dataset detected, processing in chunks of {chunk_size}"
            )
            geometry_series = []
            for i in range(0, len(df), chunk_size):
                chunk = df["geometry"].iloc[i: i + chunk_size]
                chunk_geom = gpd.GeoSeries.from_wkb(chunk.apply(bytes))
                geometry_series.append(chunk_geom)
            df["geometry"] = pd.concat(geometry_series, ignore_index=True)
        else:
            df["geometry"] = gpd.GeoSeries.from_wkb(
                df["geometry"].apply(bytes)
            )

        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")
        geojson = json.loads(gdf.to_json())

        geojson = create_ogc_geojson_response(
            geojson,
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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load collection '{collection_id}': {str(e)}",
        ) from e
