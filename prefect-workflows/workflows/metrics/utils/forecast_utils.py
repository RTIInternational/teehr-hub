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
        .metrics(table_name=joined_forecast_table_name).
        add_calculated_fields([
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
        .metrics(table_name=joined_forecast_table_name)
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
    # Build the WHERE clause for configuration filtering
    where_clause = ""
    if forecast_configuration_names:
        # Convert list to SQL IN clause format
        config_list = "', '".join(forecast_configuration_names)
        where_clause = f"WHERE configuration_name IN ('{config_list}')"
        logger.info(
            f"Filtering to configurations: {forecast_configuration_names}"
        )

    joined_sdf = ev.spark.sql(f"""
        WITH filtered_secondary AS (
            SELECT * FROM iceberg.teehr.secondary_timeseries
            {where_clause}
        )
        SELECT /*+ BROADCAST(cf) */
            fs.reference_time
            , fs.value_time
            , pf.location_id as primary_location_id
            , fs.location_id as secondary_location_id
            , pf.value as primary_value
            , fs.value as secondary_value
            , fs.configuration_name
            , fs.unit_name
            , fs.variable_name
            , fs.member
        FROM filtered_secondary fs
        JOIN iceberg.teehr.location_crosswalks cf
            ON cf.secondary_location_id = fs.location_id
        JOIN iceberg.teehr.primary_timeseries pf
            ON cf.primary_location_id = pf.location_id
            AND fs.value_time = pf.value_time
            AND fs.unit_name = pf.unit_name
            AND fs.variable_name = pf.variable_name
    """)
    logger.info("Joined timeseries table created.")
    return joined_sdf
