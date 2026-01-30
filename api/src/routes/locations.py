"""
Locations collection endpoints (OGC API Features).
"""

import json
import time

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from ..config import config
from ..database import execute_query, trino_catalog, trino_schema
from .utils import create_ogc_geojson_response

router = APIRouter()


@router.get("/collections/locations/items")
async def get_locations_items(
    request: Request,
    bbox: str | None = Query(
        None, description="Bounding box (minLon,minLat,maxLon,maxLat)"
    ),
    prefix: str | None = Query(
        None, description="Location ID prefix to filter by (e.g., 'usgs', 'nwm')"
    ),
    include_attributes: bool = Query(
        False, description="Include pivoted location attributes as properties"
    ),
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get location features (OGC API Features endpoint).

    By default returns just location id, name, and geometry.
    Set include_attributes=true to include all location attributes as properties.
    Use prefix to filter by location ID prefix (e.g., 'usgs', 'nwm').
    """
    try:
        # Build prefix filter if provided
        prefix_filter = f"l.id LIKE '{prefix}-%'" if prefix else "1=1"

        if include_attributes:
            # Query locations with their attributes (one row per attribute)
            base_query = f"""
                SELECT
                    l.id,
                    l.name,
                    l.geometry,
                    la.attribute_name,
                    la.value as attribute_value
                FROM {trino_catalog}.{trino_schema}.locations l
                LEFT JOIN {trino_catalog}.{trino_schema}.location_attributes la
                    ON l.id = la.location_id
                WHERE {prefix_filter}
            """
        else:
            # Simple query without attributes
            base_query = f"""
                SELECT
                    l.id,
                    l.name,
                    l.geometry
                FROM {trino_catalog}.{trino_schema}.locations l
                WHERE {prefix_filter}
            """

        spatial_filters = []

        if bbox:
            try:
                coords_list = list(map(float, bbox.split(",")))
                if len(coords_list) == 4:
                    min_lon, min_lat, max_lon, max_lat = coords_list
                    spatial_filters.append(f"""
                        ST_Within(
                            ST_GeomFromBinary(geometry),
                            ST_Envelope(
                                ST_GeometryFromText(
                                    'LINESTRING(
                                        {min_lon} {min_lat},
                                        {max_lon} {max_lat}
                                    )'
                                )
                            )
                        )
                    """)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid bbox format. Use: minLon,minLat,maxLon,maxLat"
                    ),
                ) from None

        if spatial_filters:
            base_query += " AND " + " AND ".join(spatial_filters)

        # Add ordering
        if include_attributes:
            base_query += " ORDER BY l.id"
        else:
            base_query += f" ORDER BY id OFFSET {offset} LIMIT {limit}"

        query_start = time.time()
        df = execute_query(base_query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        # Pivot attributes if requested, otherwise df is already paginated
        if include_attributes:
            # First, separate location columns from attribute columns
            location_cols = ["id", "name", "geometry"]
            locations_df = df[location_cols].drop_duplicates(subset=["id"])

            # Pivot attributes if they exist
            if df["attribute_name"].notna().any():
                attrs_df = df[df["attribute_name"].notna()][
                    ["id", "attribute_name", "attribute_value"]
                ]
                if not attrs_df.empty:
                    attrs_pivot = attrs_df.pivot(
                        index="id",
                        columns="attribute_name",
                        values="attribute_value"
                    ).reset_index()
                    # Merge pivoted attributes back to locations
                    df = locations_df.merge(attrs_pivot, on="id", how="left")
                else:
                    df = locations_df
            else:
                df = locations_df

            # Apply pagination after pivot (since we grouped rows)
            df = df.iloc[offset: offset + limit]

        print(f"Processing {len(df)} location records")

        geojson = create_ogc_geojson_response(
            df,
            str(request.url),
            collection_id="locations",
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
            detail=f"Database error: {str(e)}"
        ) from e
