"""
Configuration settings for the TEEHR API.
"""
import os

class Config:
    """Application configuration."""
    
    # Timeout settings
    WORKER_TIMEOUT = int(os.environ.get("WORKER_TIMEOUT", "300"))  # 5 minutes
    REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))  # 5 minutes
    DB_TIMEOUT = int(os.environ.get("DB_TIMEOUT", "300"))  # 5 minutes
    
    # Query limits (not used for now)
    # MAX_ROWS_DEFAULT = int(os.environ.get("MAX_ROWS_DEFAULT", "50000"))
    # MAX_TIMESERIES_DEFAULT = int(os.environ.get("MAX_TIMESERIES_DEFAULT", "10000"))
    
    # Performance settings
    CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "1000"))
    MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
    
    # Database settings
    TRINO_HOST = os.environ.get("TRINO_HOST", "localhost")
    TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
    TRINO_USER = os.environ.get("TRINO_USER", "teehr")
    TRINO_CATALOG = os.environ.get("TRINO_CATALOG", "iceberg")
    TRINO_SCHEMA = os.environ.get("TRINO_SCHEMA", "teehr")
    
    # CORS settings
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")
    
    # Logging
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


config = Config()