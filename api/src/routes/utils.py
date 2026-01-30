"""
Utility functions for OGC API compliance.
"""

import re
import json
import time
from datetime import UTC, datetime
import pandas as pd
import geopandas as gpd

from ..config import config


def parse_datetime_parameter(datetime_param: str | None) -> tuple:
    """Parse OGC datetime parameter (ISO 8601).

    Supports:
    - Single datetime: "2020-01-01T00:00:00Z"
    - Interval: "2020-01-01T00:00:00Z/2020-12-31T23:59:59Z"
    - Open start: "../2020-12-31T23:59:59Z"
    - Open end: "2020-01-01T00:00:00Z/.."

    Returns:
        tuple: (start_datetime, end_datetime) or (None, None)
    """
    if not datetime_param:
        return None, None

    # Handle interval (with slash)
    if "/" in datetime_param:
        parts = datetime_param.split("/")
        start_str, end_str = parts[0], parts[1]

        if start_str == "..":
            start_dt = None
        else:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))

        if end_str == "..":
            end_dt = None
        else:
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

        return start_dt, end_dt
    else:
        # Single datetime - treat as exact match
        dt = datetime.fromisoformat(datetime_param.replace("Z", "+00:00"))
        return dt, dt


def parse_coords_parameter(coords: str | None) -> dict | None:
    """Parse OGC coords parameter.

    Supports WKT-like syntax:
    - POINT(lon lat)
    - POLYGON((lon lat, lon lat, ...))

    Returns:
        dict with 'type' and 'coordinates', or None if coords is empty
    """
    if not coords:
        return None

    coords = coords.strip()

    if coords.upper().startswith("POINT"):
        # Extract coordinates from POINT(lon lat)
        coords_str = coords[coords.index("(") + 1 : coords.index(")")].strip()
        lon, lat = map(float, coords_str.split())
        return {"type": "Point", "lon": lon, "lat": lat}

    # Add more geometry types as needed
    return None


def create_ogc_geojson_response(
    df: pd.DataFrame,
    request_url: str,
    number_matched: int | None = None,
    collection_id: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    """Add OGC-compliant metadata and links to a GeoJSON response.

    Args:
        df: Input DataFrame with geometry column
        request_url: URL of the current request
        number_matched: Total number of features matching query
        collection_id: Collection identifier for link generation
        limit: Current page size for pagination links
        offset: Current offset for pagination links
    """
    # Process geometry in chunks for large datasets
    format_start = time.time()
    
    if df.empty:
        geojson = {"type": "FeatureCollection", "features": []}
    else:
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

    # Set feature id from properties if available
    for feature in geojson.get("features", []):
        if "id" in feature.get("properties", {}):
            feature["id"] = feature["properties"].get("id")
        if "location_id" in feature.get("properties", {}):
            feature["id"] = feature["properties"].get("location_id")
        if "primary_location_id" in feature.get("properties", {}):
            feature["id"] = feature["properties"].get("primary_location_id")

    # Add timestamp
    geojson["timeStamp"] = datetime.now(UTC).isoformat()

    # Add number fields
    number_returned = len(geojson.get("features", []))
    geojson["numberReturned"] = number_returned

    if number_matched is not None:
        geojson["numberMatched"] = number_matched
    else:
        geojson["numberMatched"] = number_returned

    # Parse base URL for pagination links
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(request_url)
    query_params = parse_qs(parsed.query)

    # Add links
    links = [
        {
            "href": request_url,
            "rel": "self",
            "type": "application/geo+json",
            "title": "This document",
        }
    ]

    if collection_id:
        links.append(
            {
                "href": f"/collections/{collection_id}",
                "rel": "collection",
                "type": "application/json",
                "title": "The collection document",
            }
        )

    # Add pagination links if applicable
    # Pagination happens here because the attributes may have been 
    # pivoted from rows to columns.
    if limit is not None and offset is not None:
        # Next link (if we returned a full page)
        if number_returned == limit:
            next_offset = offset + limit
            query_params["offset"] = [str(next_offset)]
            query_params["limit"] = [str(limit)]
            next_query = urlencode({k: v[0] for k, v in query_params.items()})
            next_url = urlunparse(parsed._replace(query=next_query))
            links.append(
                {
                    "href": next_url,
                    "rel": "next",
                    "type": "application/geo+json",
                    "title": "Next page",
                }
            )

        # Previous link (if not on first page)
        if offset > 0:
            prev_offset = max(0, offset - limit)
            query_params["offset"] = [str(prev_offset)]
            query_params["limit"] = [str(limit)]
            prev_query = urlencode({k: v[0] for k, v in query_params.items()})
            prev_url = urlunparse(parsed._replace(query=prev_query))
            links.append(
                {
                    "href": prev_url,
                    "rel": "prev",
                    "type": "application/geo+json",
                    "title": "Previous page",
                }
            )

    geojson["links"] = links

    format_time = time.time() - format_start
    print(f"Formatting to GeoJSON time: {format_time:.3f} seconds")
    
    return geojson
