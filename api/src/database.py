"""
Database connection and query utilities.
"""

import pandas as pd
import geopandas as gpd
from trino.dbapi import connect
import os
import re
import logging
from typing import Optional, List, Dict, Any
from .models import MetricsTable
from .config import config
import time
from functools import lru_cache

# Configure logging
logger = logging.getLogger("teehr-api.database")


# Trino connection configuration from config
trino_host = config.TRINO_HOST
trino_port = config.TRINO_PORT
trino_user = config.TRINO_USER
trino_catalog = config.TRINO_CATALOG
trino_schema = config.TRINO_SCHEMA

# Connection pool settings from config
MAX_RETRIES = config.MAX_RETRIES
RETRY_DELAY = 1  # seconds

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


def execute_query(query: str, max_rows: Optional[int] = None, retry_count: int = 0) -> pd.DataFrame:
    """Execute a query and return results as a pandas DataFrame.
    
    Args:
        query: SQL query to execute
        max_rows: Maximum number of rows to return (only applied if specified)
        retry_count: Current retry attempt
    """
    logger.info(f"Executing query (attempt {retry_count + 1}/{MAX_RETRIES + 1}): {query[:200]}...")
    
    # Only add LIMIT clause if max_rows is explicitly specified
    if max_rows and "LIMIT" not in query.upper():
        query = f"{query} LIMIT {max_rows}"
        logger.info(f"Added LIMIT {max_rows} to query")
    
    try:
        with get_trino_connection() as conn:
            query_start = time.time()
            df = pd.read_sql(query, conn)
            query_time = time.time() - query_start
            
            logger.info(f"Query completed in {query_time:.3f} seconds, returned {len(df)} rows")
            
            # Warning for large result sets
            if len(df) > 10000:
                logger.warning(f"Large result set ({len(df)} rows) - this may cause processing delays")
            
            return df
            
    except Exception as e:
        logger.error(f"Query failed (attempt {retry_count + 1}): {str(e)}")
        
        # Retry logic for transient errors
        if retry_count < MAX_RETRIES and should_retry_error(e):
            logger.info(f"Retrying query in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY)
            return execute_query(query, max_rows, retry_count + 1)
        else:
            raise e


def should_retry_error(error: Exception) -> bool:
    """Determine if an error should trigger a retry."""
    error_str = str(error).lower()
    
    # Retry on common transient errors
    transient_errors = [
        "connection reset",
        "connection timeout", 
        "connection refused",
        "temporary failure",
        "server busy"
    ]
    
    return any(transient_error in error_str for transient_error in transient_errors)
