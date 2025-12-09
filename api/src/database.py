"""
Database connection and query utilities.
"""

import pandas as pd
import geopandas as gpd
from trino.dbapi import connect
import os
import re
from typing import Optional, List, Dict, Any
from .models import MetricsTable
import time


# Trino connection configuration
trino_host = os.environ.get("TRINO_HOST", "localhost")
trino_port = int(os.environ.get("TRINO_PORT", 8080))
trino_user = os.environ.get("TRINO_USER", "teehr")
trino_catalog = os.environ.get("TRINO_CATALOG", "iceberg")
trino_schema = os.environ.get("TRINO_SCHEMA", "teehr")

def sanitize_string(value: str) -> str:
    """
    Sanitize string to prevent SQL injection by allowing only alphanumeric characters,
    underscores, hyphens, and dots. Raise an error if invalid characters are found.
    """
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', value):
        raise ValueError(f"Invalid characters in value: {value}. Only alphanumeric characters, underscores, hyphens, and dots are allowed.")
    return value


def get_trino_connection():
    """Create and return a Trino database connection."""
    return connect(
        host=trino_host,
        port=trino_port,
        user=trino_user,
        catalog=trino_catalog,
        schema=trino_schema,
    )


def execute_query(query: str) -> pd.DataFrame:
    """Execute a query and return results as a pandas DataFrame."""
    print(f"Query: {query}")
    with get_trino_connection() as conn:
        query_start = time.time()
        df = pd.read_sql(query, conn)
        query_time = time.time() - query_start
        print(f"Query execution time: {query_time:.3f} seconds")
        return df
