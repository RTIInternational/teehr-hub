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
        where_clause = f"WHERE sf.configuration_name IN ('{config_list}')"
        logger.info(
            f"Filtering to configurations: {forecast_configuration_names}"
        )

    joined_sdf = ev.sql(f"""
        SELECT
            sf.reference_time
            , sf.value_time as value_time
            , pf.location_id as primary_location_id
            , sf.location_id as secondary_location_id
            , pf.value as primary_value
            , sf.value as secondary_value
            , sf.configuration_name
            , sf.unit_name
            , sf.variable_name
            , sf.member
        FROM secondary_timeseries sf
        JOIN location_crosswalks cf
            on cf.secondary_location_id = sf.location_id
        JOIN primary_timeseries pf
            on cf.primary_location_id = pf.location_id
            and sf.value_time = pf.value_time
            and sf.unit_name = pf.unit_name
            and sf.variable_name = pf.variable_name
        {where_clause}
        """,
        create_temp_views=[
            "secondary_timeseries",
            "location_crosswalks",
            "primary_timeseries"
        ]
    )
    logger.info("Joined timeseries table created.")
    return joined_sdf
