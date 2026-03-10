"""
Custom metrics analytics implementation.

This analytics allows users to specify:
- Source table
- Filters
- Calculated fields
- Group by columns
- Metrics to calculate
"""

import logging
from typing import Any, Dict, List, Optional

import teehr
from teehr import DeterministicMetrics as dm
from teehr import Signatures as s
from teehr import RowLevelCalculatedFields as rcf

from .base import BaseAnalytics

logger = logging.getLogger(__name__)

# Result schema for analytics outputs
RESULT_CATALOG = "iceberg"
RESULT_SCHEMA = "teehr_results"


# ============================================================================
# Metric name to teehr class mapping
# ============================================================================

METRIC_FACTORIES = {
    # Signatures (single field metrics)
    "count": lambda **kw: s.Count(**_filter_kwargs(s.Count, kw)),
    "minimum": lambda **kw: s.Minimum(**_filter_kwargs(s.Minimum, kw)),
    "maximum": lambda **kw: s.Maximum(**_filter_kwargs(s.Maximum, kw)),
    "average": lambda **kw: s.Average(**_filter_kwargs(s.Average, kw)),
    "sum": lambda **kw: s.Sum(**_filter_kwargs(s.Sum, kw)),
    "variance": lambda **kw: s.Variance(**_filter_kwargs(s.Variance, kw)),
    "max_value_time": lambda **kw: s.MaxValueTime(**_filter_kwargs(s.MaxValueTime, kw)),
    "flow_duration_curve_slope": lambda **kw: s.FlowDurationCurveSlope(**_filter_kwargs(s.FlowDurationCurveSlope, kw)),

    # Deterministic metrics (primary vs secondary)
    "mean_error": lambda **kw: dm.MeanError(**_filter_kwargs(dm.MeanError, kw)),
    "relative_bias": lambda **kw: dm.RelativeBias(**_filter_kwargs(dm.RelativeBias, kw)),
    "multiplicative_bias": lambda **kw: dm.MultiplicativeBias(**_filter_kwargs(dm.MultiplicativeBias, kw)),
    "mean_absolute_error": lambda **kw: dm.MeanAbsoluteError(**_filter_kwargs(dm.MeanAbsoluteError, kw)),
    "mean_absolute_relative_error": lambda **kw: dm.MeanAbsoluteRelativeError(**_filter_kwargs(dm.MeanAbsoluteRelativeError, kw)),
    "mean_square_error": lambda **kw: dm.MeanSquareError(**_filter_kwargs(dm.MeanSquareError, kw)),
    "root_mean_square_error": lambda **kw: dm.RootMeanSquareError(**_filter_kwargs(dm.RootMeanSquareError, kw)),
    "nash_sutcliffe_efficiency": lambda **kw: dm.NashSutcliffeEfficiency(**_filter_kwargs(dm.NashSutcliffeEfficiency, kw)),
    "normalized_nash_sutcliffe_efficiency": lambda **kw: dm.NormalizedNashSutcliffeEfficiency(**_filter_kwargs(dm.NormalizedNashSutcliffeEfficiency, kw)),
    "kling_gupta_efficiency": lambda **kw: dm.KlingGuptaEfficiency(**_filter_kwargs(dm.KlingGuptaEfficiency, kw)),
    "kling_gupta_efficiency_mod1": lambda **kw: dm.KlingGuptaEfficiencyMod1(**_filter_kwargs(dm.KlingGuptaEfficiencyMod1, kw)),
    "kling_gupta_efficiency_mod2": lambda **kw: dm.KlingGuptaEfficiencyMod2(**_filter_kwargs(dm.KlingGuptaEfficiencyMod2, kw)),
    "pearson_correlation": lambda **kw: dm.PearsonCorrelation(**_filter_kwargs(dm.PearsonCorrelation, kw)),
    "spearman_correlation": lambda **kw: dm.SpearmanCorrelation(**_filter_kwargs(dm.SpearmanCorrelation, kw)),
    "r_squared": lambda **kw: dm.Rsquared(**_filter_kwargs(dm.Rsquared, kw)),
    "root_mean_standard_deviation_ratio": lambda **kw: dm.RootMeanStandardDeviationRatio(**_filter_kwargs(dm.RootMeanStandardDeviationRatio, kw)),
    "annual_peak_relative_bias": lambda **kw: dm.AnnualPeakRelativeBias(**_filter_kwargs(dm.AnnualPeakRelativeBias, kw)),
    "max_value_delta": lambda **kw: dm.MaxValueDelta(**_filter_kwargs(dm.MaxValueDelta, kw)),
    "max_value_time_delta": lambda **kw: dm.MaxValueTimeDelta(**_filter_kwargs(dm.MaxValueTimeDelta, kw)),
}


# ============================================================================
# Calculated field mapping
# ============================================================================

CALCULATED_FIELD_FACTORIES = {
    "month": lambda **kw: rcf.Month(**_filter_kwargs(rcf.Month, kw)),
    "year": lambda **kw: rcf.Year(**_filter_kwargs(rcf.Year, kw)),
    "water_year": lambda **kw: rcf.WaterYear(**_filter_kwargs(rcf.WaterYear, kw)),
    "seasons": lambda **kw: rcf.Seasons(**_filter_kwargs(rcf.Seasons, kw)),
    "day_of_year": lambda **kw: rcf.DayOfYear(**_filter_kwargs(rcf.DayOfYear, kw)),
    "hour_of_year": lambda **kw: rcf.HourOfYear(**_filter_kwargs(rcf.HourOfYear, kw)),
    "forecast_lead_time": lambda **kw: rcf.ForecastLeadTime(**_filter_kwargs(rcf.ForecastLeadTime, kw)),
    "forecast_lead_time_bins": lambda **kw: rcf.ForecastLeadTimeBins(**_filter_kwargs(rcf.ForecastLeadTimeBins, kw)),
}


def _filter_kwargs(cls, kwargs: dict) -> dict:
    """Filter kwargs to only include fields accepted by the class."""
    # Get field names from the class
    if hasattr(cls, "model_fields"):
        valid_fields = set(cls.model_fields.keys())
    else:
        valid_fields = set()
    return {k: v for k, v in kwargs.items() if k in valid_fields and v is not None}


def _build_filter_clause(filters: List[Dict]) -> str:
    """Build SQL WHERE clause from filters.

    Note: This is a simplified implementation. In production, consider
    using parameterized queries or the teehr filter API.
    """
    if not filters:
        return ""

    clauses = []
    for f in filters:
        col = f["column"]
        op = f["operator"]
        val = f["value"]

        if op == "in":
            if isinstance(val, list):
                formatted_vals = ", ".join(
                    f"'{v}'" if isinstance(v, str) else str(v)
                    for v in val
                )
                clauses.append(f"{col} IN ({formatted_vals})")
        elif op == "like":
            clauses.append(f"{col} LIKE '{val}'")
        elif op in ("=", ">", "<", ">=", "<="):
            if isinstance(val, str):
                clauses.append(f"{col} {op} '{val}'")
            else:
                clauses.append(f"{col} {op} {val}")

    return " AND ".join(clauses) if clauses else ""


class CustomMetricsAnalytics(BaseAnalytics):
    """Analytics for custom metric queries."""

    def run(
        self,
        ev: teehr.Evaluation,
        run_id: str,
        parameters: Dict[str, Any],
    ) -> str:
        """Run custom metrics analytics.

        Parameters
        ----------
        ev : teehr.Evaluation
            The teehr evaluation object.
        run_id : str
            Unique run identifier.
        parameters : dict
            Request parameters with keys:
            - source_table: str
            - filters: Optional[List[dict]]
            - calculated_fields: Optional[List[dict]]
            - group_by: List[str]
            - metrics: List[dict]
            - order_by: Optional[List[str]]

        Returns
        -------
        str
            Result table name.
        """
        source_table = parameters["source_table"]
        filters = parameters.get("filters", [])
        calculated_fields = parameters.get("calculated_fields", [])
        group_by = parameters["group_by"]
        metrics_config = parameters["metrics"]
        order_by = parameters.get("order_by", [])

        logger.info(f"Running custom metrics on {source_table}")
        logger.info(f"Group by: {group_by}")
        logger.info(f"Metrics: {[m['name'] for m in metrics_config]}")

        # Build metrics list
        metrics = []
        for m in metrics_config:
            name = m["name"]
            if name not in METRIC_FACTORIES:
                raise ValueError(f"Unknown metric: {name}")

            # Build kwargs from metric config
            kwargs = {
                "add_epsilon": m.get("add_epsilon", False),
                "transform": m.get("transform"),
                # KGE-specific
                "sr": m.get("sr"),
                "sa": m.get("sa"),
                "sb": m.get("sb"),
                # FDC-specific
                "lower_quantile": m.get("lower_quantile"),
                "upper_quantile": m.get("upper_quantile"),
            }
            metrics.append(METRIC_FACTORIES[name](**kwargs))

        # Build calculated fields list
        calc_fields = []
        for cf in calculated_fields:
            field_type = cf["field_type"]
            if field_type not in CALCULATED_FIELD_FACTORIES:
                raise ValueError(f"Unknown calculated field: {field_type}")

            kwargs = {
                "input_field_name": cf.get("input_field_name"),
                "output_field_name": cf.get("output_field_name"),
                "bin_size": cf.get("bin_size"),
            }
            calc_fields.append(CALCULATED_FIELD_FACTORIES[field_type](**kwargs))

        # Build query
        query_builder = ev.metrics(table_name=source_table)

        # Add calculated fields
        if calc_fields:
            query_builder = query_builder.add_calculated_fields(calc_fields)

        # Execute query
        logger.info("Executing metrics query...")
        sdf = query_builder.query(
            include_metrics=metrics,
            group_by=group_by,
            order_by=order_by if order_by else None,
        ).to_sdf()

        # Apply post-query filters if needed
        # Note: For now, filters should be applied during query construction
        # This is a simplified approach - full filter support would use teehr's filter API
        if filters:
            filter_clause = _build_filter_clause(filters)
            if filter_clause:
                sdf.createOrReplaceTempView("results_temp")
                sdf = ev.spark.sql(f"SELECT * FROM results_temp WHERE {filter_clause}")

        # Generate result table name
        result_table = f"run_{run_id.replace('-', '_')}"

        # Write to results schema
        logger.info(f"Writing results to {RESULT_SCHEMA}.{result_table}...")

        # Use direct Spark SQL to write to the results schema
        # since ev.write.to_warehouse writes to the main teehr schema
        full_table_name = f"{RESULT_CATALOG}.{RESULT_SCHEMA}.{result_table}"
        sdf.writeTo(full_table_name).createOrReplace()

        logger.info(f"Results written to {full_table_name}")
        return result_table
