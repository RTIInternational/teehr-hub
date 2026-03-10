"""
Pydantic models for the async analytics API.

These models define the request/response contracts for submitting
Spark-based analytics jobs and retrieving results.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
import hashlib
import json


# ============================================================================
# Enums - These mirror teehr package enums for API validation
# ============================================================================

class FilterOperatorEnum(str, Enum):
    """Filter operators for analytics queries.

    Mirrors teehr.models.filters.FilterOperators.
    """
    eq = "="
    gt = ">"
    lt = "<"
    gte = ">="
    lte = "<="
    islike = "like"
    isin = "in"


class TransformEnum(str, Enum):
    """Transform methods for metrics.

    Mirrors teehr.models.metrics.basemodels.TransformEnum.
    """
    log = "log"
    sqrt = "sqrt"
    square = "square"
    cube = "cube"
    exp = "exp"
    inv = "inv"
    abs = "abs"
    none = "none"


class MetricNameEnum(str, Enum):
    """Available metrics for API queries.

    Maps to teehr DeterministicMetrics and Signatures classes.
    """
    # Signatures (single field)
    count = "count"
    minimum = "minimum"
    maximum = "maximum"
    average = "average"
    sum = "sum"
    variance = "variance"
    max_value_time = "max_value_time"
    flow_duration_curve_slope = "flow_duration_curve_slope"

    # Deterministic metrics (primary vs secondary)
    mean_error = "mean_error"
    relative_bias = "relative_bias"
    multiplicative_bias = "multiplicative_bias"
    mean_absolute_error = "mean_absolute_error"
    mean_absolute_relative_error = "mean_absolute_relative_error"
    mean_square_error = "mean_square_error"
    root_mean_square_error = "root_mean_square_error"
    nash_sutcliffe_efficiency = "nash_sutcliffe_efficiency"
    normalized_nash_sutcliffe_efficiency = "normalized_nash_sutcliffe_efficiency"
    kling_gupta_efficiency = "kling_gupta_efficiency"
    kling_gupta_efficiency_mod1 = "kling_gupta_efficiency_mod1"
    kling_gupta_efficiency_mod2 = "kling_gupta_efficiency_mod2"
    pearson_correlation = "pearson_correlation"
    spearman_correlation = "spearman_correlation"
    r_squared = "r_squared"
    root_mean_standard_deviation_ratio = "root_mean_standard_deviation_ratio"
    annual_peak_relative_bias = "annual_peak_relative_bias"
    max_value_delta = "max_value_delta"
    max_value_time_delta = "max_value_time_delta"


class CalculatedFieldEnum(str, Enum):
    """Available row-level calculated fields.

    Maps to teehr RowLevelCalculatedFields classes.
    """
    month = "month"
    year = "year"
    water_year = "water_year"
    seasons = "seasons"
    day_of_year = "day_of_year"
    hour_of_year = "hour_of_year"
    forecast_lead_time = "forecast_lead_time"
    forecast_lead_time_bins = "forecast_lead_time_bins"


class SourceTableEnum(str, Enum):
    """Source tables available for analytics queries."""
    joined_forecast_timeseries = "joined_forecast_timeseries"
    joined_simulation_timeseries = "joined_simulation_timeseries"
    joined_timeseries = "joined_timeseries"


class RunStatusEnum(str, Enum):
    """Status of an analytics run."""
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


# ============================================================================
# Request Models
# ============================================================================

class APIFilter(BaseModel):
    """Filter for analytics query.

    Simplified from teehr.TableFilter - no context-based validation.
    """
    column: str = Field(
        ...,
        description="Column name to filter on"
    )
    operator: FilterOperatorEnum = Field(
        ...,
        description="Filter operator"
    )
    value: Union[str, int, float, datetime, List[Union[str, int, float, datetime]]] = Field(
        ...,
        description="Filter value (use list for 'in' operator)"
    )

    @field_validator("value")
    @classmethod
    def validate_in_operator(cls, v, info):
        """Ensure 'in' operator has a list value."""
        if info.data.get("operator") == FilterOperatorEnum.isin:
            if not isinstance(v, list):
                raise ValueError("'in' operator requires a list value")
        elif isinstance(v, list):
            raise ValueError("List values can only be used with 'in' operator")
        return v


class MetricRequest(BaseModel):
    """Metric configuration for API query."""
    name: MetricNameEnum = Field(
        ...,
        description="Metric name"
    )
    transform: Optional[TransformEnum] = Field(
        default=None,
        description="Transform to apply to values before metric calculation"
    )
    add_epsilon: bool = Field(
        default=False,
        description="Add epsilon to avoid division by zero"
    )
    # KGE-specific scaling factors
    sr: Optional[float] = Field(
        default=None,
        description="KGE correlation scaling factor (default: 1.0)"
    )
    sa: Optional[float] = Field(
        default=None,
        description="KGE alpha (variability) scaling factor (default: 1.0)"
    )
    sb: Optional[float] = Field(
        default=None,
        description="KGE beta (bias) scaling factor (default: 1.0)"
    )
    # Flow duration curve specific
    lower_quantile: Optional[float] = Field(
        default=None,
        description="Lower quantile for FDC slope (default: 0.25)"
    )
    upper_quantile: Optional[float] = Field(
        default=None,
        description="Upper quantile for FDC slope (default: 0.85)"
    )


class CalculatedFieldConfig(BaseModel):
    """Configuration for a calculated field."""
    field_type: CalculatedFieldEnum = Field(
        ...,
        description="Type of calculated field to add"
    )
    # Field-specific parameters
    input_field_name: Optional[str] = Field(
        default=None,
        description="Input field name (default varies by field type)"
    )
    output_field_name: Optional[str] = Field(
        default=None,
        description="Output field name (default: field_type name)"
    )
    # ForecastLeadTimeBins specific
    bin_size: Optional[str] = Field(
        default=None,
        description="Bin size for lead time bins, e.g., '6 hours'"
    )


class AnalyticsRunRequest(BaseModel):
    """Request to create a new analytics run.

    This is the main input for the POST /analytics/{analytics_id}/runs endpoint.
    """
    source_table: SourceTableEnum = Field(
        ...,
        description="Source table to query"
    )
    filters: Optional[List[APIFilter]] = Field(
        default=None,
        description="Filters to apply to source data"
    )
    calculated_fields: Optional[List[CalculatedFieldConfig]] = Field(
        default=None,
        description="Calculated fields to add before aggregation"
    )
    group_by: List[str] = Field(
        ...,
        min_length=1,
        description="Columns to group by for metric aggregation"
    )
    metrics: List[MetricRequest] = Field(
        ...,
        min_length=1,
        description="Metrics to calculate"
    )
    order_by: Optional[List[str]] = Field(
        default=None,
        description="Columns to order results by"
    )

    def compute_cache_key(self, analytics_id: str, version: str = "1") -> str:
        """Compute cache key for this request.

        Cache key is a hash of normalized request parameters.
        """
        # Create a canonical representation
        canonical = {
            "analytics_id": analytics_id,
            "version": version,
            "source_table": self.source_table.value,
            "filters": [
                {"column": f.column, "operator": f.operator.value, "value": f.value}
                for f in (self.filters or [])
            ],
            "calculated_fields": [
                cf.model_dump(exclude_none=True)
                for cf in (self.calculated_fields or [])
            ],
            "group_by": sorted(self.group_by),
            "metrics": [
                m.model_dump(exclude_none=True)
                for m in self.metrics
            ],
        }
        # Sort and hash
        json_str = json.dumps(canonical, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]


# ============================================================================
# Response Models
# ============================================================================

class AnalyticsRunResponse(BaseModel):
    """Response after creating an analytics run."""
    run_id: str = Field(
        ...,
        description="Unique identifier for this run"
    )
    analytics_id: str = Field(
        ...,
        description="Analytics type identifier"
    )
    status: RunStatusEnum = Field(
        ...,
        description="Current status of the run"
    )
    cache_key: str = Field(
        ...,
        description="Cache key for this request"
    )
    cached: bool = Field(
        default=False,
        description="Whether result was returned from cache"
    )
    created_at: datetime = Field(
        ...,
        description="When the run was created"
    )
    result_table: Optional[str] = Field(
        default=None,
        description="Name of result table (when succeeded)"
    )


class AnalyticsRunStatusResponse(BaseModel):
    """Response for analytics run status query."""
    run_id: str
    analytics_id: str
    status: RunStatusEnum
    cache_key: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result_catalog: str = Field(default="iceberg")
    result_schema: str = Field(default="teehr_results")
    result_table: Optional[str] = None
    error_message: Optional[str] = None
    job_name: Optional[str] = Field(
        default=None,
        description="Kubernetes Job name for debugging"
    )


class AnalyticsResultRow(BaseModel):
    """Single row of analytics results."""
    model_config = {"extra": "allow"}

    # Results are dynamic based on group_by and metrics
    # So we allow extra fields


class AnalyticsResultsResponse(BaseModel):
    """Response containing analytics results."""
    run_id: str
    analytics_id: str
    status: RunStatusEnum
    total_rows: Optional[int] = Field(
        default=None,
        description="Total number of rows in result"
    )
    offset: int = Field(default=0)
    limit: int = Field(default=1000)
    rows: List[dict[str, Any]] = Field(
        default_factory=list,
        description="Result rows"
    )
    links: Optional[dict[str, str]] = Field(
        default=None,
        description="Pagination links"
    )


# ============================================================================
# Internal Models (for run tracking table)
# ============================================================================

class AnalyticsRunRecord(BaseModel):
    """Model for analytics_runs tracking table record."""
    run_id: str
    analytics_id: str
    cache_key: str
    status: RunStatusEnum
    parameters_json: str
    result_table: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_message: Optional[str] = None
