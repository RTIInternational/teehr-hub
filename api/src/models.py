"""
Database models and enums for the TEEHR API.
"""

from enum import Enum
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class MetricsTable(str, Enum):
    """Available metrics table names."""
    SIM_METRICS_BY_LOCATION = "sim_metrics_by_location"
    FCST_METRICS_BY_LOCATION = "fcst_metrics_by_location"


# class LocationResponse(BaseModel):
#     """Response model for location data."""
#     location_id: str
#     geometry: Dict[str, Any]
#     properties: Optional[Dict[str, Any]] = None


# class MetricResponse(BaseModel):
#     """Response model for metric data."""
#     location_id: str
#     configuration: str
#     variable: str
#     metric_name: str
#     metric_value: float
#     reference_time: Optional[datetime] = None
#     value_time: Optional[datetime] = None


# class TimeseriesPoint(BaseModel):
#     """Single point in a timeseries."""
#     value_time: datetime
#     value: float


# class TimeseriesResponse(BaseModel):
#     """Response model for timeseries data."""
#     location_id: str
#     configuration: Optional[str] = None
#     variable: str
#     unit: Optional[str] = None
#     timeseries: List[TimeseriesPoint]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str