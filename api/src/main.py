from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import geopandas as gpd
from trino.dbapi import connect
import os
from typing import Optional, List, Dict, Any
import json
from datetime import datetime
import re
import time

app = FastAPI(title="TEEHR Dashboard API", version="0.1.0")

# CORS middleware to allow frontend requests - MUST be first middleware
# Get the allowed origins from environment or use defaults
cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
print(f"DEBUG: CORS_ORIGINS from environment: {cors_origins_env}")

if cors_origins_env == "*":
    # In development, allow all origins
    allow_origins = ["*"]
    allow_credentials = False
    print("DEBUG: Using wildcard CORS origins")
else:
    # In production, use specific origins from environment
    allow_origins = [origin.strip() for origin in cors_origins_env.split(",")]
    allow_credentials = True
    print(f"DEBUG: Using specific CORS origins from config: {allow_origins}")

# Add CORS middleware FIRST - this is critical
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=600,
)

# Trino connection configuration
TRINO_HOST = os.environ.get("TRINO_HOST", "localhost")
TRINO_PORT = int(os.environ.get("TRINO_PORT", 8080))
TRINO_USER = os.environ.get("TRINO_USER", "teehr")
TRINO_CATALOG = os.environ.get("TRINO_CATALOG", "iceberg")
TRINO_SCHEMA = os.environ.get("TRINO_SCHEMA", "teehr")

def sanitize_string(value: str) -> str:
    """Sanitize string to only allow safe characters for SQL queries."""
    if not value:
        return ""
    # Allow only alphanumeric, underscore, hyphen, periods, and spaces for identifiers
    return re.sub(r'[^a-zA-Z0-9_\-. ]', '', value)

def validate_datetime_string(value: str) -> str:
    """Validate and sanitize datetime string for SQL queries."""
    if not value:
        return ""
    # Allow only characters valid in ISO datetime format: digits, hyphens, colons, spaces, T
    sanitized = re.sub(r'[^0-9\-: T]', '', value)
    
    # Basic validation - check if it looks like a datetime
    datetime_pattern = r'^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$|^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$'
    if not re.match(datetime_pattern, sanitized):
        raise ValueError(f"Invalid datetime format: {value}")
    
    return sanitized

def get_trino_connection():
    """Establishes and returns a Trino database connection."""
    try:
        conn = connect(
            host=TRINO_HOST,
            user=TRINO_USER,
            catalog=TRINO_CATALOG,
            schema=TRINO_SCHEMA,
            http_scheme='http',
            port=TRINO_PORT,
        )
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main dashboard page."""
    with open("frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/api/locations")
async def get_locations():
    """Get all USGS locations from the main locations table."""
    try:
        conn = get_trino_connection()
        
        # Simple query - all USGS locations
        query = """
        SELECT 
            id as location_id,
            name,
            geometry
        FROM iceberg.teehr.locations 
        WHERE id LIKE 'usgs-%'
        """
        
        print(f"Locations query: {query}")  # Debug log
        
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        
        locations = []
        from shapely import wkb
        
        for row in rows:
            try:
                location_id = row[0]
                name = row[1] or location_id  # Use ID as name if name is null
                geom_bytes = row[2]
                
                if geom_bytes:
                    # Parse WKB geometry to get coordinates
                    point = wkb.loads(geom_bytes)
                    latitude = point.y
                    longitude = point.x
                    
                    locations.append({
                        "location_id": location_id,
                        "name": name,
                        "latitude": latitude,
                        "longitude": longitude
                    })
            except Exception as geom_error:
                print(f"Warning: Could not parse geometry for {location_id}: {geom_error}")
                continue
        
        cursor.close()
        conn.close()
        
        print(f"Successfully loaded {len(locations)} locations from database")
        return locations
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load locations: {str(e)}")


@app.get("/api/metrics")
async def get_metrics(
    configuration: Optional[str] = None,
    variable: Optional[str] = None
):
    """Get simulation metrics by location with optional filtering, returns GeoJSON."""
    try:
        conn = get_trino_connection()
        
        params = []
        where_conditions = ["primary_location_id LIKE 'usgs-%'"]
        
        if configuration:
            where_conditions.append("configuration_name = ?")
            params.append(configuration)
        if variable:
            where_conditions.append("variable_name = ?")
            params.append(variable)
        
        where_clause = " AND ".join(where_conditions)
        
        query = f"""
        SELECT 
            primary_location_id as location_id,
            configuration_name,
            variable_name,
            unit_name,
            count,
            average,
            relative_bias,
            nash_sutcliffe_efficiency,
            kling_gupta_efficiency,
            name,
            geometry
        FROM iceberg.teehr.sim_metrics_by_location 
        WHERE {where_clause}
        """
        
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        
        if df.empty:
            return {
                "type": "FeatureCollection", 
                "features": []
            }
        
        df["geometry"] = gpd.GeoSeries.from_wkb(
            df["geometry"].apply(lambda x: bytes(x))
        )
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326", geometry="geometry")
        # Use the proper geopandas >=1.0.0 method
        return gdf.to_geo_dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load metrics: {str(e)}")


@app.get("/api/metric-names")
async def get_metric_names():
    """Get all available metric column names dynamically from the database."""
    try:
        conn = get_trino_connection()
        
        # Query to get all column names from the sim_metrics_by_location table
        query = """
        SELECT column_name
        FROM information_schema.columns 
        WHERE table_schema = 'teehr' 
        AND table_name = 'sim_metrics_by_location'
        ORDER BY column_name
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        # Get all column names
        all_columns = df['column_name'].tolist()
        
        # Filter out non-metric columns
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


@app.get("/api/configurations")
async def get_configurations():
    """Get all available configurations."""
    try:
        conn = get_trino_connection()
        
        query = "SELECT DISTINCT configuration_name FROM iceberg.teehr.sim_metrics_by_location ORDER BY configuration_name"
        df = pd.read_sql(query, conn)
        conn.close()
        return df['configuration_name'].tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load configurations: {str(e)}")


@app.get("/api/variables")
async def get_variables():
    """Get all available variables."""
    try:
        conn = get_trino_connection()
        
        query = "SELECT DISTINCT variable_name FROM iceberg.teehr.sim_metrics_by_location ORDER BY variable_name"
        df = pd.read_sql(query, conn)
        conn.close()
        return df['variable_name'].tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load variables: {str(e)}")


@app.get("/api/timeseries/primary/{location_id}")
async def get_primary_timeseries(
    location_id: str,
    configuration: Optional[str] = None,
    variable: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """Get primary timeseries data for a specific location."""
    try:
        conn = get_trino_connection()
        
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
        FROM iceberg.teehr.primary_timeseries 
        WHERE {where_clause}
        ORDER BY value_time
        """
        
        print(f"Primary timeseries query: {query}")  # Debug log
        
        # Time the query execution
        query_start = time.time()
        df = pd.read_sql(query, conn)
        conn.close()
        query_time = time.time() - query_start
        print(f"Primary query execution time: {query_time:.3f} seconds")
        
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


@app.get("/api/timeseries/secondary/{location_id}")
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
        conn = get_trino_connection()
        
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
        FROM iceberg.teehr.secondary_timeseries st
        JOIN iceberg.teehr.location_crosswalks lc
        ON st.location_id = lc.secondary_location_id
        WHERE {where_clause}
        ORDER BY st.value_time
        """
        
        print(f"Secondary timeseries query: {query}")  # Debug log
        
        # Time the query execution
        query_start = time.time()
        df = pd.read_sql(query, conn)
        conn.close()
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)