"""
Analytics registry mapping analytics_id to handler classes.
"""

from .analytics.custom_metrics import CustomMetricsAnalytics

# Registry of available analytics
ANALYTICS_REGISTRY = {
    "custom_metrics": CustomMetricsAnalytics,
}
