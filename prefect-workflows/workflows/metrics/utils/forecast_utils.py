from typing import List
import logging

from prefect import get_run_logger, task
from prefect.cache_policies import NO_CACHE
from pyspark.sql import DataFrame

import teehr
from teehr import DeterministicMetrics as dm
from teehr import RowLevelCalculatedFields as rcf
from teehr import Signatures as s

logging.getLogger("teehr").setLevel(logging.INFO)

FORECAST_BY_LEAD_TIME_BIN_GROUPBY = [
    "primary_location_id",
    "secondary_location_id",
    "configuration_name",
    "forecast_lead_time_bin",
    "variable_name",
    "unit_name",
    "member"
]
FORECAST_BY_LOCATION_GROUPBY = [
    "primary_location_id",
    "secondary_location_id",
    "configuration_name",
    "unit_name",
    "variable_name",
    "member"
]

count = s.Count()
rmsdr = dm.RootMeanStandardDeviationRatio()
rbias = dm.RelativeBias()
nse = dm.NashSutcliffeEfficiency()
kge = dm.KlingGuptaEfficiency()

rmsdr.add_epsilon = True
rbias.add_epsilon = True
nse.add_epsilon = True
kge.add_epsilon = True

FORECAST_METRICS = [
    count,
    rmsdr,
    rbias,
    nse,
    kge
]


@task(cache_policy=NO_CACHE)
def calculate_forecast_metrics_by_lead_time_bins(
    ev: teehr.Evaluation,
    joined_forecast_table_name: str,
) -> DataFrame:
    """Calculate forecast metrics by lead time.

    Notes
    -----
    - This requires the joined forecast table to be created first.
    """
    logger = get_run_logger()
    logger.info("Creating forecast metrics by lead time bins table...")

    sdf = (
        ev
        .table(joined_forecast_table_name)
        .add_calculated_fields([
            rcf.ForecastLeadTimeBins(
                bin_size="6 hours"
            )
        ])
        .query(
            include_metrics=FORECAST_METRICS,
            group_by=FORECAST_BY_LEAD_TIME_BIN_GROUPBY,
        ).to_sdf()
    )
    sdf.createOrReplaceTempView("forecast_metrics")

    sdf = ev.spark.sql("""
        SELECT m.*, l.*
        FROM forecast_metrics m
        JOIN iceberg.teehr.locations l
        ON l.id = m.primary_location_id
    """)
    sdf = sdf.drop("id")
    return sdf


@task(cache_policy=NO_CACHE)
def calculate_forecast_metrics_by_location(
    ev: teehr.Evaluation,
    joined_forecast_table_name: str,
) -> DataFrame:
    """Calculate forecast metrics by location.

    Notes
    -----
    - This requires the joined forecast table to be created first.
    """
    logger = get_run_logger()
    logger.info("Creating forecast metrics by location table...")

    sdf = (
        ev
        .table(joined_forecast_table_name)
        .add_calculated_fields([
            rcf.ForecastLeadTimeBins(
                bin_size="6 hours"
            )
        ])
        .query(
            include_metrics=FORECAST_METRICS,
            group_by=FORECAST_BY_LOCATION_GROUPBY
        ).to_sdf()
    )

    sdf.createOrReplaceTempView("forecast_metrics")

    sdf = ev.spark.sql("""
        SELECT m.*, l.*
        FROM forecast_metrics m
        JOIN iceberg.teehr.locations l
        ON l.id = m.primary_location_id
    """)
    sdf = sdf.drop("id")
    return sdf


@task(cache_policy=NO_CACHE)
def join_forecast_timeseries(
    ev: teehr.Evaluation,
    forecast_configuration_names: List[str]
) -> DataFrame:
    """Join secondary forecasts with primary timeseries.

    Notes
    -----
    - Joins secondary timeseries whose configuration names are
      in the provided list to primary timeseries via the location
      crosswalk.
    """
    logger = get_run_logger()
    logger.info("Creating joined forecast timeseries table...")

    secondary_filters = None
    if forecast_configuration_names:
        secondary_filters=[
            {
                "column": "configuration_name",
                "operator": "in",
                "value": forecast_configuration_names
            }
        ]
    
    joined_sdf = ev.joined_timeseries_view(
        secondary_filters=secondary_filters
    ).to_sdf()

    return joined_sdf
