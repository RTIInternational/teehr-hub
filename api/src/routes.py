"""
API routes for the TEEHR Dashboard.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
import pandas as pd
import geopandas as gpd
import json
from typing import Optional, List
from datetime import datetime
import time

from .models import (
    MetricsTable,
    HealthResponse
)
from .database import (
    execute_query, sanitize_string, trino_catalog, trino_schema
)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def root():
    """Serve a simple HTML page with link to docs."""
    return """
    <html><body>
        <h1>TEEHR Dashboard API v1</h1>
        <p><a href="/docs">API Documentation</a></p>
    </body></html>
    """


@router.get("/api/locations")
async def get_locations():
    """Get all available location geometries."""
    try:
        query = f"""
        SELECT 
            id as location_id,
            name,
            geometry
        FROM {trino_catalog}.{trino_schema}.locations 
        WHERE id LIKE 'usgs-%'
        """
        
        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")
        
        if df.empty:
            return {"type": "FeatureCollection", "features": []}
        
        # Convert to GeoDataFrame
        df["geometry"] = gpd.GeoSeries.from_wkb(
            df["geometry"].apply(lambda x: bytes(x))
        )
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")
        
        # Use the proper geopandas >=1.0.0 method
        # return gdf.to_geo_dict()
        geojson = json.loads(gdf.to_json())
        
        return geojson
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/api/metrics")
async def get_metrics(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query"),
    configuration: Optional[str] = Query(None, description="Filter by configuration"),
    variable: Optional[str] = Query(None, description="Filter by variable"),
):
    """Get simulation metrics by location with optional filtering, returns GeoJSON."""
    try:
        
        where_conditions = ["primary_location_id LIKE 'usgs-%'"]
        
        if configuration:
            sanitized_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{sanitized_configuration}'")
        if variable:
            sanitized_variable = sanitize_string(variable)
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
            return {"type": "FeatureCollection", "features": []}
        
        df = df.rename(columns={"primary_location_id": "location_id"})
        
        df["geometry"] = gpd.GeoSeries.from_wkb(
            df["geometry"].apply(lambda x: bytes(x))
        )
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")

        # Use the proper geopandas >=1.0.0 method
        # return gdf.to_geo_dict()
        geojson = json.loads(gdf.to_json())
        
        return geojson
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load metrics: {str(e)}")



@router.get("/api/metric-names")
async def get_metric_names(
    table: MetricsTable = Query(MetricsTable.SIM_METRICS_BY_LOCATION, description="Metrics table to query")
):
    """Get unique metric names available in the specified table."""
    try:
        # Query to get all column names from the metrics table
        table_name = sanitize_string(table.value)
        query = f"""
        SELECT column_name
        FROM information_schema.columns 
        WHERE table_schema = '{trino_schema}' 
        AND table_name = '{table_name}'
        ORDER BY column_name
        """
        
        query_start = time.time()
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")
        
        # Get all column names
        all_columns = df['column_name'].tolist()
        
        # Filter out non-metric columns.  Thi is not robust but works for now.
        non_metric_columns = {
            'primary_location_id', 'location_id', 'name', 'location_name',
            'variable_name', 'configuration_name', 'unit_name',
            'geometry', 'created_at', 'updated_at'
        }
        
        # Keep only columns that are likely metrics (not in the exclusion set)
        metric_columns = [col for col in all_columns if col.lower() not in non_metric_columns]
        
        print(f"Found metric columns: {metric_columns}")
        return metric_columns
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load metrics names: {str(e)}")


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


@router.get("/api/timeseries/primary/{location_id}")
async def get_primary_timeseries(
    location_id: str,
    configuration: Optional[str] = None,
    variable: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """Get primary timeseries data for a specific location."""
    try: 
        # Build conditions for filtering with safe string interpolation
        safe_location_id = sanitize_string(location_id)
        where_conditions = [f"location_id = '{safe_location_id}'"]
        
        if start_date:
            where_conditions.append(f"value_time >= TIMESTAMP '{start_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if end_date:
            where_conditions.append(f"value_time <= TIMESTAMP '{end_date.strftime('%Y-%m-%d %H:%M:%S')}'")
        if variable:
            safe_variable = sanitize_string(variable)
            where_conditions.append(f"variable_name = '{safe_variable}'")
        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"configuration_name = '{safe_configuration}'")
        
        where_clause = " AND ".join(where_conditions)
        
        # Get primary timeseries data
        query = f"""
        SELECT 
            'primary' as series_type,
            location_id,
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
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")
        
        # Check if we have any data
        if df.empty:
            print(f"No primary timeseries data found for location {location_id}")
            return []
        
        print(f"Query returned {len(df)} primary timeseries records")

        # Time the formatting
        format_start = time.time()
        # Convert timestamp to string for JSON serialization
        df['value_time'] = pd.to_datetime(df['value_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        if 'reference_time' in df.columns:
            # Handle null reference times by filling with a placeholder
            df['reference_time'] = df['reference_time'].fillna('null')
            # Convert non-null values to string
            mask = df['reference_time'] != 'null'
            if mask.any():
                df.loc[mask, 'reference_time'] = pd.to_datetime(df.loc[mask, 'reference_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            df['reference_time'] = 'null'

        # Group by series metadata and create nested structure
        grouped = df.groupby(['series_type', 'location_id', 'reference_time', 'configuration_name', 'variable_name', 'unit_name'])
        
        data = []
        for (series_type, location_id, reference_time, configuration_name, variable_name, unit_name), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "location_id": location_id,
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
        return data
        
    except Exception as e:
        print(f"Primary timeseries error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load primary timeseries for location {location_id}: {str(e)}")


@router.get("/api/timeseries/secondary/{location_id}")
async def get_secondary_timeseries(
    location_id: str,
    configuration: Optional[str] = None,
    variable: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    reference_start_date: Optional[datetime] = None,
    reference_end_date: Optional[datetime] = None
):
    """Get secondary timeseries data for a specific location."""
    try:
        # Build conditions for filtering - using the crosswalk join pattern with safe string interpolation
        safe_location_id = sanitize_string(location_id)
        where_conditions = [f"lc.primary_location_id = '{safe_location_id}'"]
        
        if configuration:
            safe_configuration = sanitize_string(configuration)
            where_conditions.append(f"st.configuration_name = '{safe_configuration}'")
        if variable:
            safe_variable = sanitize_string(variable)
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
            lc.primary_location_id as location_id,
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
        df = execute_query(query)
        query_time = time.time() - query_start
        print(f"Secondary query execution time: {query_time:.3f} seconds")
        
        # Check if we have any data
        if df.empty:
            print(f"No secondary timeseries data found for location {location_id}")
            return []
        
        print(f"Query returned {len(df)} secondary timeseries records")

        # Time the formatting
        format_start = time.time()
        # Convert timestamp to string for JSON serialization
        df['value_time'] = pd.to_datetime(df['value_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        if 'reference_time' in df.columns:
            # Handle null reference times by filling with a placeholder
            df['reference_time'] = df['reference_time'].fillna('null')
            # Convert non-null values to string
            mask = df['reference_time'] != 'null'
            if mask.any():
                df.loc[mask, 'reference_time'] = pd.to_datetime(df.loc[mask, 'reference_time']).dt.strftime('%Y-%m-%d %H:%M:%S')
        else:
            df['reference_time'] = 'null'
        
        # Debug: Print column info
        print(f"DataFrame columns: {list(df.columns)}")
        print(f"Sample data: {df.head()}")
        
        # Fill null members with a placeholder for grouping
        df['member'] = df['member'].fillna('null')
        
        # Group by series metadata and create nested structure
        grouped = df.groupby(['series_type', 'location_id', 'reference_time', 'configuration_name', 'variable_name', 'unit_name', 'member'])
        
        data = []
        for (series_type, location_id, reference_time, configuration_name, variable_name, unit_name, member), group in grouped:
            timeseries_data = {
                "series_type": series_type,
                "location_id": location_id,
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
        return data
        
    except Exception as e:
        print(f"Secondary timeseries error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load secondary timeseries for location {location_id}: {str(e)}")


# @router.get("/health", response_model=HealthResponse)
# async def health_check():
#     """Health check endpoint."""
#     return HealthResponse(
#         status="healthy",
#         timestamp=datetime.utcnow(),
#         version="0.1.0"
#     )