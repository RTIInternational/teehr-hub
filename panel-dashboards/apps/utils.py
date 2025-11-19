import pandas as pd
from trino.dbapi import connect
import os

from typing import Union
import datetime


def get_trino_connection():
    """Establishes and returns a Trino database connection."""
    # Trino connection configuration
    TRINO_HOST = os.environ.get("TRINO_HOST", "localhost")
    TRINO_PORT = os.environ.get("TRINO_PORT", 8080)
    TRINO_USER = os.environ.get("TRINO_USER", "teehr")
    TRINO_CATALOG = os.environ.get("TRINO_CATALOG", "iceberg")
    TRINO_SCHEMA = os.environ.get("TRINO_SCHEMA", "teehr")

    conn = connect(
        host=TRINO_HOST,
        user=TRINO_USER,
        catalog=TRINO_CATALOG,
        schema=TRINO_SCHEMA,
        http_scheme='http',
        port=TRINO_PORT,
        # For production, add authentication:
        # auth=BasicAuthentication("username", "password")
    )
    return conn

def get_primary_timeseries(
    location_id: str, 
    start_date: Union[str, datetime.datetime, pd.Timestamp, None] = None, 
    end_date: Union[str, datetime.datetime, pd.Timestamp, None] = None
):
    """Fetches primary timeseries data for a given location from the Trino database and returns it as a DataFrame."""
    conn = get_trino_connection()
    
    def format_date(date_input):
        """Convert various date formats to string format for SQL."""
        if date_input is None:
            return None
        if isinstance(date_input, str):
            return date_input
        elif isinstance(date_input, (datetime.datetime, pd.Timestamp)):
            return date_input.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Try to convert to string
            return str(date_input)
    
    # Build the WHERE clause
    where_conditions = [f"location_id = '{location_id}'"]
    
    # Add date filters if provided
    if start_date:
        formatted_start = format_date(start_date)
        where_conditions.append(f"value_time >= TIMESTAMP '{formatted_start}'")
    if end_date:
        formatted_end = format_date(end_date)
        where_conditions.append(f"value_time <= TIMESTAMP '{formatted_end}'")
    
    where_clause = " AND ".join(where_conditions)
    
    sql = f"SELECT * FROM iceberg.teehr.primary_timeseries WHERE {where_clause}"
    df = pd.read_sql(sql, conn)
    
    return df


def get_secondary_timeseries(
    location_id: str, 
    configuration_names: list = ["nwm30_retrospective"], 
    start_date: Union[str, datetime.datetime, pd.Timestamp, None] = None, 
    end_date: Union[str, datetime.datetime, pd.Timestamp, None] = None
):
    """Fetches secondary timeseries data for a given primary location from the Trino database and returns it as a DataFrame."""
    conn = get_trino_connection()
    
    def format_date(date_input):
        """Convert various date formats to string format for SQL."""
        if date_input is None:
            return None
        if isinstance(date_input, str):
            return date_input
        elif isinstance(date_input, (datetime.datetime, pd.Timestamp)):
            return date_input.strftime('%Y-%m-%d %H:%M:%S')
        else:
            # Try to convert to string
            return str(date_input)
    
    def build_config_in_clause(config_list):
        """Build the IN clause for configuration names to avoid nested quotes."""
        quoted_configs = [f"'{config}'" for config in config_list]
        return f"({','.join(quoted_configs)})"
    
    # Build the WHERE clause
    where_conditions = [f"lc.primary_location_id = '{location_id}'"]
    
    # Add configuration filter only if configuration_names is not None and not empty
    if configuration_names:
        config_in_clause = build_config_in_clause(configuration_names)
        where_conditions.append(f"configuration_name IN {config_in_clause}")
    
    # Add date filters if provided
    if start_date:
        formatted_start = format_date(start_date)
        where_conditions.append(f"st.value_time >= TIMESTAMP '{formatted_start}'")
    if end_date:
        formatted_end = format_date(end_date)
        where_conditions.append(f"st.value_time <= TIMESTAMP '{formatted_end}'")
    
    where_clause = " AND ".join(where_conditions)
    
    sql = f"""
        SELECT st.* 
        FROM iceberg.teehr.secondary_timeseries st
        JOIN location_crosswalks lc
        ON st.location_id = lc.secondary_location_id
        WHERE {where_clause}
    """
    df = pd.read_sql(sql, conn)
    
    return df
