"""
Models package for the TEEHR API.

Re-exports all models for backward compatibility.
"""

# Re-export existing OGC models (from original models.py location)
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel


class MetricsTable(str, Enum):
    """Available metrics table names."""
    SIM_METRICS_BY_LOCATION = "sim_metrics_by_location"
    FCST_METRICS_BY_LOCATION = "fcst_metrics_by_location"
    FCST_METRICS_BY_LEAD_TIME_BINS = "fcst_metrics_by_lead_time_bins"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    version: str


# OGC API Models

class Link(BaseModel):
    """OGC API Link object."""
    href: str
    rel: str
    type: str | None = None
    title: str | None = None
    hreflang: str | None = None


class ConformanceResponse(BaseModel):
    """OGC API Conformance declaration."""
    conformsTo: list[str]


class Extent(BaseModel):
    """OGC API Extent object."""
    spatial: dict[str, Any] | None = None
    temporal: dict[str, Any] | None = None


class Collection(BaseModel):
    """OGC API Collection metadata."""
    id: str
    title: str
    description: str
    links: list[Link]
    extent: Extent | None = None
    itemType: str | None = None
    crs: list[str] | None = None


class CollectionsResponse(BaseModel):
    """OGC API Collections list."""
    links: list[Link]
    collections: list[Collection]


class LandingPage(BaseModel):
    """OGC API Landing page."""
    title: str
    description: str
    links: list[Link]


# Export analytics models
from .analytics import (
    FilterOperatorEnum,
    MetricNameEnum,
    TransformEnum,
    CalculatedFieldEnum,
    SourceTableEnum,
    RunStatusEnum,
    APIFilter,
    MetricRequest,
    CalculatedFieldConfig,
    AnalyticsRunRequest,
    AnalyticsRunResponse,
    AnalyticsRunStatusResponse,
    AnalyticsResultsResponse,
)

__all__ = [
    # OGC models
    "MetricsTable",
    "HealthResponse",
    "Link",
    "ConformanceResponse",
    "Extent",
    "Collection",
    "CollectionsResponse",
    "LandingPage",
    # Analytics models
    "FilterOperatorEnum",
    "MetricNameEnum",
    "TransformEnum",
    "CalculatedFieldEnum",
    "SourceTableEnum",
    "RunStatusEnum",
    "APIFilter",
    "MetricRequest",
    "CalculatedFieldConfig",
    "AnalyticsRunRequest",
    "AnalyticsRunResponse",
    "AnalyticsRunStatusResponse",
    "AnalyticsResultsResponse",
]
