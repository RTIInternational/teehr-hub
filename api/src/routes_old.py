"""
API routes for the TEEHR Dashboard.
"""

import json
import time
from datetime import UTC, datetime

import geopandas as gpd
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .config import config
from .database import (
    execute_query,
    get_trino_connection,
    sanitize_string,
    trino_catalog,
    trino_schema,
)
from .models import (
    Collection,
    CollectionsResponse,
    ConformanceResponse,
    Extent,
    LandingPage,
    Link,
    MetricsTable,
)

router = APIRouter()


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
    if '/' in datetime_param:
        parts = datetime_param.split('/')
        start_str, end_str = parts[0], parts[1]

        start_dt = None if start_str == '..' else datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_dt = None if end_str == '..' else datetime.fromisoformat(end_str.replace('Z', '+00:00'))

        return start_dt, end_dt
    else:
        # Single datetime - treat as exact match or you could do a range
        dt = datetime.fromisoformat(datetime_param.replace('Z', '+00:00'))
        return dt, dt


def parse_coords_parameter(coords: str | None) -> dict:
    """Parse OGC coords parameter.
    
    Supports WKT-like syntax:
    - POINT(lon lat)
    - POLYGON((lon lat, lon lat, ...))
    
    Returns:
        dict with 'type' and 'coordinates'
    """
    if not coords:
        return None

    coords = coords.strip()

    if coords.upper().startswith('POINT'):
        # Extract coordinates from POINT(lon lat)
        coords_str = coords[coords.index('(')+1:coords.index(')')].strip()
        lon, lat = map(float, coords_str.split())
        return {'type': 'Point', 'lon': lon, 'lat': lat}

    # Add more geometry types as needed
    return None


def create_ogc_geojson_response(
    geojson: dict,
    request_url: str,
    number_matched: int | None = None,
    collection_id: str | None = None
) -> dict:
    """Add OGC-compliant metadata and links to a GeoJSON response.
    
    Args:
        geojson: Base GeoJSON FeatureCollection
        request_url: URL of the current request
        number_matched: Total number of features matching query
        collection_id: Collection identifier for link generation
    """
    # Add timestamp
    geojson["timeStamp"] = datetime.now(UTC).isoformat()

    # Add number fields
    number_returned = len(geojson.get("features", []))
    geojson["numberReturned"] = number_returned

    if number_matched is not None:
        geojson["numberMatched"] = number_matched
    else:
        geojson["numberMatched"] = number_returned

    # Add links
    links = [
        {
            "href": request_url,
            "rel": "self",
            "type": "application/geo+json",
            "title": "This document"
        }
    ]

    if collection_id:
        links.append({
            "href": f"/collections/{collection_id}",
            "rel": "collection",
            "type": "application/json",
            "title": "The collection document"
        })

    geojson["links"] = links

    return geojson


def create_coveragejson_timeseries(
    timeseries_data: list,
    location_id: str,
    location_coords: tuple | None = None
) -> dict:
    """Convert timeseries data to CoverageJSON format (OGC EDR standard).
    
    Args:
        timeseries_data: List of timeseries objects from database
        location_id: Location identifier
        location_coords: Optional (lon, lat) tuple for the location
        
    Returns:
        CoverageJSON Coverage object
    """
    if not timeseries_data:
        return {
            "type": "Coverage",
            "domain": {
                "type": "Domain",
                "axes": {"t": {"values": []}}
            },
            "parameters": {},
            "ranges": {}
        }

    # Group by parameter/variable
    parameters_data = {}
    for series in timeseries_data:
        param_name = series.get('variable_name', 'unknown')
        if param_name not in parameters_data:
            parameters_data[param_name] = {
                'unit': series.get('unit_name', ''),
                'configuration': series.get('configuration_name', ''),
                'times': [],
                'values': []
            }

        # Add timeseries points
        for point in series.get('timeseries', []):
            parameters_data[param_name]['times'].append(point['value_time'])
            parameters_data[param_name]['values'].append(point['value'])

    # Build CoverageJSON structure
    # Get all unique times across all parameters
    all_times = sorted(set(
        time
        for param_data in parameters_data.values()
        for time in param_data['times']
    ))

    # Build domain
    domain = {
        "type": "Domain",
        "axes": {
            "t": {
                "values": all_times
            }
        }
    }

    # Add spatial coordinates if available
    if location_coords:
        domain["axes"]["x"] = {"values": [location_coords[0]]}
        domain["axes"]["y"] = {"values": [location_coords[1]]}

    # Build parameters
    parameters = {}
    ranges = {}

    for param_name, param_data in parameters_data.items():
        parameters[param_name] = {
            "type": "Parameter",
            "description": {
                "en": f"{param_name} - {param_data['configuration']}"
            },
            "unit": {
                "label": {"en": param_data['unit']},
                "symbol": param_data['unit']
            },
            "observedProperty": {
                "id": param_name,
                "label": {"en": param_name}
            }
        }

        # Build ranges - align values with domain times
        time_value_map = dict(zip(param_data['times'], param_data['values']))
        aligned_values = [
            time_value_map.get(t, None) for t in all_times
        ]

        ranges[param_name] = {
            "type": "NdArray",
            "dataType": "float",
            "axisNames": ["t"],
            "shape": [len(all_times)],
            "values": aligned_values
        }

    return {
        "type": "Coverage",
        "domain": domain,
        "parameters": parameters,
        "ranges": ranges
    }


@router.get("/", response_model=LandingPage)
async def root():
    """OGC API Landing page with links to all resources."""
    return LandingPage(
        title="TEEHR Dashboard API",
        description="OGC-compliant API for hydrological timeseries and metrics data",
        links=[
            Link(
                href="/",
                rel="self",
                type="application/json",
                title="This document"
            ),
            Link(
                href="/api",
                rel="service-desc",
                type="application/vnd.oai.openapi+json;version=3.0",
                title="API definition"
            ),
            Link(
                href="/docs",
                rel="service-doc",
                type="text/html",
                title="API documentation"
            ),
            Link(
                href="/conformance",
                rel="conformance",
                type="application/json",
                title="OGC API conformance classes"
            ),
            Link(
                href="/collections",
                rel="data",
                type="application/json",
                title="Collections"
            ),
        ]
    )


@router.get("/conformance", response_model=ConformanceResponse)
async def conformance():
    """OGC API conformance declaration."""
    return ConformanceResponse(
        conformsTo=[
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/landing-page",
            "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
            "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
            "http://www.opengis.net/spec/ogcapi-edr-1/1.0/conf/core",
        ]
    )


@router.get("/collections", response_model=CollectionsResponse)
async def get_collections():
    """List all available data collections."""

    # Get extent information from database
    try:
        # Get spatial extent from locations
        # Note: geometry is stored as WKB (varbinary), need to convert
        spatial_query = f"""
        SELECT 
            MIN(ST_X(ST_GeomFromBinary(geometry))) as min_lon,
            MAX(ST_X(ST_GeomFromBinary(geometry))) as max_lon,
            MIN(ST_Y(ST_GeomFromBinary(geometry))) as min_lat,
            MAX(ST_Y(ST_GeomFromBinary(geometry))) as max_lat
        FROM {trino_catalog}.{trino_schema}.locations
        WHERE id LIKE 'usgs-%'
        """

        # Get temporal extent from timeseries
        temporal_query = f"""
        SELECT 
            MIN(value_time) as min_time,
            MAX(value_time) as max_time
        FROM (
            SELECT value_time 
            FROM {trino_catalog}.{trino_schema}.primary_timeseries
            UNION ALL
            SELECT value_time 
            FROM {trino_catalog}.{trino_schema}.secondary_timeseries
        )
        """

        spatial_df = execute_query(spatial_query, max_rows=1)
        temporal_df = execute_query(temporal_query, max_rows=1)

        # Build extent
        spatial_extent = {
            "bbox": [[
                float(spatial_df['min_lon'].iloc[0]),
                float(spatial_df['min_lat'].iloc[0]),
                float(spatial_df['max_lon'].iloc[0]),
                float(spatial_df['max_lat'].iloc[0])
            ]],
            "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
        }

        temporal_extent = {
            "interval": [[
                temporal_df['min_time'].iloc[0].isoformat() + "Z",
                temporal_df['max_time'].iloc[0].isoformat() + "Z"
            ]],
            "trs": "http://www.opengis.net/def/uom/ISO-8601/0/Gregorian"
        }

    except Exception as e:
        print(f"Warning: Could not calculate extents: {e}")
        spatial_extent = None
        temporal_extent = None

    collections = [
        Collection(
            id="locations",
            title="Observation Locations",
            description="Geographic locations where observations are collected",
            links=[
                Link(href="/collections/locations", rel="self", type="application/json"),
                Link(href="/collections/locations/items", rel="items", type="application/geo+json"),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
        ),
        Collection(
            id="primary_timeseries",
            title="Primary Timeseries",
            description="Observed timeseries data at monitoring locations",
            links=[
                Link(href="/collections/primary_timeseries", rel="self", type="application/json"),
                Link(href="/collections/primary_timeseries/position", rel="data", type="application/json"),
            ],
            extent=Extent(spatial=spatial_extent, temporal=temporal_extent) if spatial_extent and temporal_extent else None,
            crs=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
        ),
        Collection(
            id="secondary_timeseries",
            title="Secondary Timeseries",
            description="Forecast/simulated timeseries data",
            links=[
                Link(href="/collections/secondary_timeseries", rel="self", type="application/json"),
                Link(href="/collections/secondary_timeseries/position", rel="data", type="application/json"),
            ],
            extent=Extent(spatial=spatial_extent, temporal=temporal_extent) if spatial_extent and temporal_extent else None,
            crs=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
        ),
        Collection(
            id="metrics",
            title="Performance Metrics",
            description="Computed performance metrics by location",
            links=[
                Link(href="/collections/metrics", rel="self", type="application/json"),
                Link(href="/collections/metrics/items", rel="items", type="application/geo+json"),
            ],
            extent=Extent(spatial=spatial_extent) if spatial_extent else None,
            itemType="feature",
            crs=["http://www.opengis.net/def/crs/OGC/1.3/CRS84"]
        ),
    ]

    return CollectionsResponse(
        links=[
            Link(href="/collections", rel="self", type="application/json"),
            Link(href="/", rel="root", type="application/json"),
        ],
        collections=collections
    )


@router.get("/collections/{collection_id}", response_model=Collection)
async def get_collection(collection_id: str):
    """Get metadata for a specific collection."""

    # Get the collections list
    collections_response = await get_collections()

    # Find the requested collection
    for collection in collections_response.collections:
        if collection.id == collection_id:
            return collection

    raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found")


@router.get("/collections/locations/items")
async def get_collection_locations_items(
    request: Request,
    bbox: str | None = Query(None, description="Bounding box filter"),
    limit: int | None = Query(None, description="Maximum number of items to return")
):
    """Get items from the locations collection (OGC API Features endpoint)."""
    # Delegate to existing locations endpoint
    return await get_locations(request, coords=None, bbox=bbox, f=None)


@router.get("/collections/metrics/items")
async def get_collection_metrics_items(
    request: Request,
    primary_location_id: str | None = Query(None, description="Filter by location"),
    configuration: str | None = Query(None, description="Filter by configuration"),
    parameter_name: str | None = Query(None, description="Filter by parameter/variable name"),
    bbox: str | None = Query(None, description="Bounding box filter"),
):
    """Get items from the metrics collection (OGC API Features endpoint)."""
    # Delegate to existing metrics endpoint
    return await get_metrics(
        request=request,
        table=MetricsTable.SIM_METRICS_BY_LOCATION,
        primary_location_id=primary_location_id,
        configuration=configuration,
        parameter_name=parameter_name,
        f=None
    )


@router.get("/api/locations")
async def get_locations(
    request: Request,
    coords: str | None = Query(None, description="OGC coords parameter (e.g., POINT(-74.78 43.01))"),
    bbox: str | None = Query(None, description="Bounding box (minLon,minLat,maxLon,maxLat)"),
    f: str | None = Query(None, description="Response format (json, html)")
):
    """Get all available location geometries.
    
    Supports spatial filtering via:
    - coords: Point-based query (e.g., POINT(-74.78 43.01))
    - bbox: Bounding box query (minLon,minLat,maxLon,maxLat)
    """
    try:
        # Base query
        base_query = f"""
        SELECT 
            id as primary_location_id,
            name,
            geometry
        FROM {trino_catalog}.{trino_schema}.locations 
        WHERE id LIKE 'usgs-%'
        """

        # Add spatial filters if provided
        spatial_filters = []

        if coords:
            coord_data = parse_coords_parameter(coords)
            if coord_data and coord_data['type'] == 'Point':
                # For point query, we could find nearest or within a radius
                # For now, just document the capability
                print(f"Point query at {coord_data['lon']}, {coord_data['lat']}")
                # Could add: ST_Distance(geometry, ST_Point(...)) < threshold

        if bbox:
            # Parse bbox: minLon,minLat,maxLon,maxLat
            try:
                coords_list = list(map(float, bbox.split(',')))
                if len(coords_list) == 4:
                    min_lon, min_lat, max_lon, max_lat = coords_list
                    spatial_filters.append(f"""
                        ST_Within(
                            ST_GeomFromBinary(geometry),
                            ST_Envelope(ST_GeometryFromText('LINESTRING({min_lon} {min_lat}, {max_lon} {max_lat})'))
                        )
                    """)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid bbox format. Use: minLon,minLat,maxLon,maxLat")

        # Combine filters
        if spatial_filters:
            base_query += " AND " + " AND ".join(spatial_filters)

        query = base_query

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        if df.empty:
            empty_response = create_ogc_geojson_response(
                {"type": "FeatureCollection", "features": []},
                str(request.url),
                collection_id="locations"
            )
            return JSONResponse(
                content=empty_response,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
                }
            )

        # Convert to GeoDataFrame with chunked processing for large datasets
        print(f"Processing {len(df)} location records")

        # Process geometry conversion in chunks to avoid memory issues
        chunk_size = config.CHUNK_SIZE
        if len(df) > chunk_size:
            print(f"Large dataset detected, processing in chunks of {chunk_size}")
            geometry_series = []
            for i in range(0, len(df), chunk_size):
                chunk = df["geometry"].iloc[i:i+chunk_size]
                chunk_geom = gpd.GeoSeries.from_wkb(
                    chunk.apply(bytes)
                )
                geometry_series.append(chunk_geom)
            df["geometry"] = pd.concat(geometry_series, ignore_index=True)
        else:
            df["geometry"] = gpd.GeoSeries.from_wkb(
                df["geometry"].apply(bytes)
            )

        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")

        # Use the proper geopandas >=1.0.0 method
        # return gdf.to_geo_dict()
        geojson = json.loads(gdf.to_json())

        # Add OGC metadata and links
        geojson = create_ogc_geojson_response(
            geojson,
            str(request.url),
            collection_id="locations"
        )

        return JSONResponse(
            content=geojson,
            headers={
                "Content-Type": "application/geo+json",
                "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/metrics")
async def get_metrics(
    request: Request,
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query"),
    primary_location_id: str | None = Query(None, description="Filter by primary location ID"),
    configuration: str | None = Query(None, description="Filter by configuration"),
    parameter_name: str | None = Query(None, description="Filter by parameter/variable name"),
    f: str | None = Query(None, description="Response format (json, html)"),
):
    """Get simulation metrics by location with optional filtering, returns OGC-compliant GeoJSON."""
    try:

        if primary_location_id:
            sanitized_location_id = sanitize_string(primary_location_id)
            where_conditions = [f"primary_location_id = '{sanitized_location_id}'"]
        else:
            where_conditions = ["primary_location_id LIKE 'usgs-%'"]

        if configuration:
            sanitized_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{sanitized_configuration}'")
        if parameter_name:
            sanitized_variable = sanitize_string(parameter_name)
            where_conditions.append(f"variable_name = '{sanitized_variable}'")

        where_clause = " AND ".join(where_conditions)

        table_name = sanitize_string(table.value)
        query = f"""
            SELECT 
                *
            FROM {trino_catalog}.{trino_schema}.{table_name}
            WHERE {where_clause}
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        if df.empty:
            empty_response = create_ogc_geojson_response(
                {"type": "FeatureCollection", "features": []},
                str(request.url),
                collection_id="metrics"
            )
            return JSONResponse(
                content=empty_response,
                headers={
                    "Content-Type": "application/geo+json",
                    "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
                }
            )

        # df = df.rename(columns={"primary_location_id": "location_id"})

        # Process geometry conversion in chunks to avoid memory issues
        chunk_size = config.CHUNK_SIZE
        if len(df) > chunk_size:
            print(f"Large dataset detected, processing in chunks of {chunk_size}")
            geometry_series = []
            for i in range(0, len(df), chunk_size):
                chunk = df["geometry"].iloc[i:i+chunk_size]
                chunk_geom = gpd.GeoSeries.from_wkb(
                    chunk.apply(bytes)
                )
                geometry_series.append(chunk_geom)
            df["geometry"] = pd.concat(geometry_series, ignore_index=True)
        else:
            df["geometry"] = gpd.GeoSeries.from_wkb(
                df["geometry"].apply(bytes)
            )

        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")

        # Use the proper geopandas >=1.0.0 method
        # return gdf.to_geo_dict()
        geojson = json.loads(gdf.to_json())

        # Add OGC metadata and links
        geojson = create_ogc_geojson_response(
            geojson,
            str(request.url),
            collection_id="metrics"
        )

        return JSONResponse(
            content=geojson,
            headers={
                "Content-Type": "application/geo+json",
                "Content-Crs": "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load metrics: {str(e)}")



@router.get("/api/table-properties")
async def get_table_properties(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query")
):
    """Get table properties including metrics, group_by, and description."""
    try:
        # Query to get table properties
        table_name = sanitize_string(table.value)

        query = f"""
            SELECT key, value FROM "{table_name}$properties"
            WHERE key IN ('metrics', 'group_by', 'description')
        """
        conn = get_trino_connection()
        cur = conn.cursor()
        cur.execute(query)
        results = cur.fetchall()

        # Build response dictionary
        properties = {}
        for key, value in results:
            if key == 'metrics':
                # Convert comma-separated string to list
                properties[key] = [s.strip() for s in value.split(",")]
            elif key == 'group_by':
                # Convert comma-separated string to list
                properties[key] = [s.strip() for s in value.split(",")]
            else:
                # Keep description as string
                properties[key] = value

        print(f"Found table properties: {properties}")
        return properties

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load table properties: {str(e)}")


@router.get("/api/table-properties-batch")
async def get_table_properties_batch(
    tables: list[MetricsTable] = Query(..., description="List of metrics tables to query")
):
    """Get table properties for multiple tables in a single request."""
    try:
        conn = get_trino_connection()
        cur = conn.cursor()

        result = {}

        for table in tables:
            table_name = sanitize_string(table.value)

            query = f"""
                SELECT key, value FROM "{table_name}$properties"
                WHERE key IN ('metrics', 'group_by', 'description')
            """

            cur.execute(query)
            table_results = cur.fetchall()

            # Build response dictionary for this table
            properties = {}
            for key, value in table_results:
                if key == 'metrics':
                    # Convert comma-separated string to list
                    properties[key] = [s.strip() for s in value.split(",")]
                elif key == 'group_by':
                    # Convert comma-separated string to list
                    properties[key] = [s.strip() for s in value.split(",")]
                else:
                    # Keep description as string
                    properties[key] = value

            result[table.value] = properties

        print(f"Found batch table properties: {result}")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load batch table properties: {str(e)}")


@router.get("/api/configurations")
async def get_configurations(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query")
):
    """Get unique configuration names."""
    try:
        table_name = sanitize_string(table.value)
        query = f"""
        SELECT DISTINCT configuration_name 
        FROM {trino_catalog}.{trino_schema}.{table_name}
        ORDER BY configuration_name
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        return df['configuration_name'].tolist() if not df.empty else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/parameters")
async def get_parameters(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query")
):
    """Get unique parameter/variable names (OGC EDR compliant)."""
    try:
        table_name = sanitize_string(table.value)
        query = f"""
        SELECT DISTINCT variable_name 
        FROM {trino_catalog}.{trino_schema}.{table_name}
        ORDER BY variable_name
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        return df['variable_name'].tolist() if not df.empty else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# Keep legacy endpoint for backward compatibility if needed
@router.get("/api/variables")
async def get_variables(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query")
):
    """Get unique variable names."""
    try:
        table_name = sanitize_string(table.value)
        query = f"""
        SELECT DISTINCT variable_name 
        FROM {trino_catalog}.{trino_schema}.{table_name}
        ORDER BY variable_name
        """

        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        return df['variable_name'].tolist() if not df.empty else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/timeseries/primary/{primary_location_id}")
async def get_primary_timeseries(
    primary_location_id: str,
    configuration: str | None = None,
    parameter_name: str | None = Query(None, description="Parameter/variable name to query"),
    datetime: str | None = Query(None, description="Datetime range (ISO 8601: start/end or ../end or start/.."),
    limit: int | None = Query(None, description="Maximum number of records to return"),
    f: str | None = Query(None, description="Response format: json (default), covjson")
):
    """Get primary timeseries data for a specific location (OGC EDR compliant).
    
    Args:
        primary_location_id: Location identifier
        configuration: Optional configuration filter
        parameter_name: Variable/parameter to query
        datetime: ISO 8601 datetime or interval (e.g., '2020-01-01T00:00:00Z/2020-12-31T23:59:59Z')
        limit: Maximum number of records
        f: Response format (json=default JSON, covjson=CoverageJSON)
    """
    try:
        # Parse OGC datetime parameter
        start_date, end_date = parse_datetime_parameter(datetime)

        # Build conditions for filtering with safe string interpolation
        safe_location_id = sanitize_string(primary_location_id)
        where_conditions = [f"location_id = '{safe_location_id}'"]

        if start_date:
            where_conditions.append(f"value_time >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if end_date:
            where_conditions.append(f"value_time <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if parameter_name:
            safe_variable = sanitize_string(parameter_name)
            where_conditions.append(f"variable_name = '{safe_variable}'")
        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{safe_configuration}'")

        where_clause = " AND ".join(where_conditions)

        # Get primary timeseries data
        query = f"""
        SELECT 
            'primary' as series_type,
            location_id as primary_location_id,
            reference_time,
            configuration_name,
            variable_name,
            unit_name,
            value_time,
            value
        FROM {trino_catalog}.{trino_schema}.primary_timeseries 
        WHERE {where_clause}
        ORDER BY value_time
        """

        query_start = time.time()
        df = execute_query(query, max_rows=limit)  # Pass limit to execute_query
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")

        # Check if we have any data
        if df.empty:
            print(f"No primary timeseries data found for location {primary_location_id}")
            return []

        print(f"Query returned {len(df)} primary timeseries records")

        # Time the formatting
        format_start = time.time()
        # Convert timestamp to string for JSON serialization
        # Ensure value_time is datetime type before using .dt accessor
        df['value_time'] = pd.to_datetime(df['value_time']).dt.strftime('%Y-%m-%d %H:%M:%S')

        if 'reference_time' in df.columns:
            # Handle null reference times safely by checking for null before fillna
            # Create mask for non-null values before any type conversion
            mask = pd.notna(df['reference_time'])
            if mask.any():
                # Convert non-null datetime values to string
                df.loc[mask, 'reference_time'] = df.loc[mask, 'reference_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            # Now fill remaining null values with 'null' string
            df['reference_time'] = df['reference_time'].fillna('null')
        else:
            df['reference_time'] = 'null'

        # Group by series metadata and create nested structure
        grouped = df.groupby(
            [
                'series_type',
                'primary_location_id',
                'reference_time',
                'configuration_name',
                'variable_name',
                'unit_name'
            ]
        )

        data = []
        for (series_type, primary_location_id, reference_time, configuration_name, variable_name, unit_name), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "primary_location_id": primary_location_id,
                "reference_time": reference_time,
                "configuration_name": configuration_name,
                "variable_name": variable_name,
                "unit_name": unit_name,
                "timeseries": group[["value_time", "value"]].to_dict(orient="records")
            }
            data.append(timeseries_data)

        format_time = time.time() - format_start
        print(f"Primary formatting time: {format_time:.3f} seconds")
        print(f"Primary total time: {query_time + format_time:.3f} seconds (query: {query_time:.3f}s, format: {format_time:.3f}s)")
        print(f"Returning {len(data)} primary timeseries")
        print(f"Format parameter f={f}")

        # Handle format negotiation
        if f and f.lower() in ['covjson', 'coveragejson']:
            # Convert to CoverageJSON
            # Get location coordinates if available
            loc_coords = None
            if not df.empty and 'geometry' in df.columns:
                try:
                    # Extract coords from first geometry
                    import geopandas as gpd
                    geom_series = gpd.GeoSeries.from_wkb(df["geometry"].iloc[0:1].apply(bytes))
                    if len(geom_series) > 0:
                        point = geom_series.iloc[0]
                        loc_coords = (point.x, point.y)
                except:
                    pass

            coverage = create_coveragejson_timeseries(
                data,
                primary_location_id,
                loc_coords
            )
            return JSONResponse(
                content=coverage,
                media_type="application/prs.coverage+json"
            )

        return data

    except Exception as e:
        print(f"Primary timeseries error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load primary timeseries for location {primary_location_id}: {str(e)}")


@router.get("/api/timeseries/secondary/{primary_location_id}")
async def get_secondary_timeseries(
    primary_location_id: str,
    configuration: str | None = None,
    parameter_name: str | None = Query(None, description="Parameter/variable name to query"),
    datetime: str | None = Query(None, description="Datetime range (ISO 8601: start/end or ../end or start/.."),
    reference_datetime: str | None = Query(None, description="Reference time range (ISO 8601)"),
    limit: int | None = Query(None, description="Maximum number of records to return"),
    f: str | None = Query(None, description="Response format: json (default), covjson")
):
    """Get secondary timeseries data for a specific location (OGC EDR compliant).
    
    Args:
        primary_location_id: Location identifier
        configuration: Optional configuration filter
        parameter_name: Variable/parameter to query
        datetime: ISO 8601 datetime or interval for value_time
        reference_datetime: ISO 8601 datetime or interval for reference_time
        limit: Maximum number of records
        f: Response format (json=default JSON, covjson=CoverageJSON)
    """
    try:
        # Parse OGC datetime parameters
        start_date, end_date = parse_datetime_parameter(datetime)
        reference_start_date, reference_end_date = parse_datetime_parameter(reference_datetime)

        # Build conditions for filtering - using the crosswalk join pattern with safe string interpolation
        safe_primary_location_id = sanitize_string(primary_location_id)
        where_conditions = [f"lc.primary_location_id = '{safe_primary_location_id}'"]

        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"st.configuration_name = '{safe_configuration}'")
        if parameter_name:
            safe_variable = sanitize_string(parameter_name)
            where_conditions.append(f"st.variable_name = '{safe_variable}'")
        if start_date:
            where_conditions.append(f"st.value_time >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if end_date:
            where_conditions.append(f"st.value_time <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if reference_start_date:
            where_conditions.append(f"st.reference_time >= TIMESTAMP '{reference_start_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if reference_end_date:
            where_conditions.append(f"st.reference_time <= TIMESTAMP '{reference_end_date.strftime('%Y-%m-%d %H:%M:%S')}'")

        where_clause = " AND ".join(where_conditions)

        # Get secondary timeseries data using crosswalk join
        query = f"""
        SELECT 
            st.value_time,
            st.value,
            st.configuration_name,
            st.variable_name,
            st.unit_name,
            st.member,
            st.reference_time,
            lc.primary_location_id as primary_location_id,
            'secondary' as series_type
        FROM {trino_catalog}.{trino_schema}.secondary_timeseries st
        JOIN {trino_catalog}.{trino_schema}.location_crosswalks lc
        ON st.location_id = lc.secondary_location_id
        WHERE {where_clause}
        ORDER BY st.value_time
        """

        print(f"Secondary timeseries query: {query}")  # Debug log

        # Time the query execution
        query_start = time.time()
        df = execute_query(query, max_rows=limit)  # Pass limit to execute_query
        query_time = time.time() - query_start
        print(f"Secondary query execution time: {query_time:.3f} seconds")

        # Check if we have any data
        if df.empty:
            print(f"No secondary timeseries data found for location {primary_location_id}")
            return []

        print(f"Query returned {len(df)} secondary timeseries records")

        # Time the formatting
        format_start = time.time()
        # Convert timestamp to string for JSON serialization
        # Ensure value_time is datetime type before using .dt accessor
        df['value_time'] = pd.to_datetime(df['value_time']).dt.strftime('%Y-%m-%d %H:%M:%S')

        if 'reference_time' in df.columns:
            # Handle null reference times safely by checking for null before fillna
            # Create mask for non-null values before any type conversion
            mask = pd.notna(df['reference_time'])
            if mask.any():
                # Convert non-null datetime values to string
                df.loc[mask, 'reference_time'] = df.loc[mask, 'reference_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
            # Now fill remaining null values with 'null' string
            df['reference_time'] = df['reference_time'].fillna('null')
        else:
            df['reference_time'] = 'null'

        # Debug: Print column info
        print(f"DataFrame columns: {list(df.columns)}")
        print(f"Sample data: {df.head()}")

        # Fill null members with a placeholder for grouping
        df['member'] = df['member'].fillna('null')

        # Group by series metadata and create nested structure
        grouped = df.groupby(['series_type', 'primary_location_id', 'reference_time', 'configuration_name', 'variable_name', 'unit_name', 'member'])

        data = []
        for (series_type, location_id, reference_time, configuration_name, variable_name, unit_name, member), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "primary_location_id": primary_location_id,
                "reference_time": reference_time if reference_time != 'null' else None,
                "configuration_name": configuration_name,
                "variable_name": variable_name,
                "unit_name": unit_name,
                "member": member if member != 'null' else None,
                "timeseries": group[["value_time", "value"]].to_dict(orient="records")
            }
            data.append(timeseries_data)

        format_time = time.time() - format_start
        print(f"Secondary formatting time: {format_time:.3f} seconds")
        print(f"Secondary total time: {query_time + format_time:.3f} seconds (query: {query_time:.3f}s, format: {format_time:.3f}s)")
        print(f"Returning {len(data)} secondary timeseries")

        # Handle format negotiation
        if f and f.lower() in ['covjson', 'coveragejson']:
            # Convert to CoverageJSON
            coverage = create_coveragejson_timeseries(
                data,
                primary_location_id,
                None  # Could add location coords if needed
            )
            return JSONResponse(
                content=coverage,
                media_type="application/prs.coverage+json"
            )

        return data

    except Exception as e:
        print(f"Secondary timeseries error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load secondary timeseries for location {primary_location_id}: {str(e)}")


@router.get("/collections/primary_timeseries/position")
async def get_primary_timeseries_position(
    coords: str = Query(..., description="POINT(lon lat) coordinates"),
    parameter_name: str | None = Query(None, description="Parameter/variable name"),
    datetime: str | None = Query(None, description="Datetime range (ISO 8601)"),
    f: str | None = Query("covjson", description="Response format: covjson (default), json")
):
    """OGC EDR position endpoint for primary timeseries.
    
    Query timeseries at a specific point location.
    """
    # Parse coordinates
    coord_data = parse_coords_parameter(coords)
    if not coord_data or coord_data['type'] != 'Point':
        raise HTTPException(status_code=400, detail="Invalid coords. Use POINT(lon lat)")

    # Find nearest location
    # For now, this is a placeholder - you'd need to implement spatial search
    # to find the location_id closest to the given coordinates
    raise HTTPException(
        status_code=501,
        detail="Position queries not yet implemented. Use /api/timeseries/primary/{location_id} instead"
    )


@router.get("/collections/secondary_timeseries/position")
async def get_secondary_timeseries_position(
    coords: str = Query(..., description="POINT(lon lat) coordinates"),
    parameter_name: str | None = Query(None, description="Parameter/variable name"),
    datetime: str | None = Query(None, description="Datetime range (ISO 8601)"),
    f: str | None = Query("covjson", description="Response format: covjson (default), json")
):
    """OGC EDR position endpoint for secondary timeseries.
    
    Query timeseries at a specific point location.
    """
    # Parse coordinates
    coord_data = parse_coords_parameter(coords)
    if not coord_data or coord_data['type'] != 'Point':
        raise HTTPException(status_code=400, detail="Invalid coords. Use POINT(lon lat)")

    # Find nearest location
    raise HTTPException(
        status_code=501,
        detail="Position queries not yet implemented. Use /api/timeseries/secondary/{location_id} instead"
    )


# @router.get("/health", response_model=HealthResponse)
# async def health_check():
#     """Health check endpoint."""
#     return HealthResponse(
#         status="healthy",
#         timestamp=datetime.utcnow(),
#         version="0.1.0"
#     )
