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
    limit: int | None = Query(
        100, ge=1, le=10000, description="Maximum number of items to return"
    ),
    offset: int | None = Query(
        0, ge=0, description="Starting index for pagination"
    ),
):
    """Get location features (OGC API Features endpoint)."""
    try:
        base_query = f"""
            SELECT
                id as primary_location_id,
                name,
                geometry
            FROM {trino_catalog}.{trino_schema}.locations
            WHERE id LIKE 'usgs-%'
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

        # Add pagination
        base_query += f" ORDER BY id OFFSET {offset} LIMIT {limit}"

        query_start = time.time()
        df = execute_query(base_query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        if df.empty:
            empty_response = create_ogc_geojson_response(
                {"type": "FeatureCollection", "features": []},
                str(request.url),
                collection_id="locations",
            )
            return JSONResponse(
                content=empty_response,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>",  # noqa: E501
                },
            )

        print(f"Processing {len(df)} location records")

        # Process geometry in chunks for large datasets
        chunk_size = config.CHUNK_SIZE
        if len(df) > chunk_size:
            print(f"Large dataset detected, processing in chunks of {chunk_size}")  # noqa: E501
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
