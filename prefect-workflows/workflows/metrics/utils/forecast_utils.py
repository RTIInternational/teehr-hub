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
def write_forecast_metrics_by_lead_time_bins(
    ev: teehr.Evaluation,
    joined_forecast_table_name: str,
    output_table_name: str
) -> DataFrame:
    """Write forecast metrics by lead time bins.

    Notes
    -----
    - This requires the joined forecast table to be created first.
    - The 'overwrite' write mode preserves history but requires the table to pre-exist.
    """
    logger = get_run_logger()
    logger.info("Creating forecast metrics by lead time bins table...")
    (
        ev
        .table(joined_forecast_table_name)
        .add_calculated_fields([
            rcf.ForecastLeadTimeBins(
                bin_size="6 hours"
            )
        ])
        .aggregate(
            metrics=FORECAST_METRICS,
            group_by=FORECAST_BY_LEAD_TIME_BIN_GROUPBY,
        )
        .add_geometry()
        .write_to(
            table_name=output_table_name,
            write_mode="overwrite"
        )
    )


@task(cache_policy=NO_CACHE)
def write_forecast_metrics_by_location(
    ev: teehr.Evaluation,
    joined_forecast_table_name: str,
    output_table_name: str
) -> DataFrame:
    """Write forecast metrics by location.

    Notes
    -----
    - This requires the joined forecast table to be created first.
    - The 'overwrite' write mode preserves history but requires the table to pre-exist.
    """
    logger = get_run_logger()
    logger.info("Creating forecast metrics by location table...")
    (
        ev
        .table(joined_forecast_table_name)
        .add_calculated_fields([
            rcf.ForecastLeadTimeBins(
                bin_size="6 hours"
            )
        ])
        .aggregate(
            metrics=FORECAST_METRICS,
            group_by=FORECAST_BY_LOCATION_GROUPBY
        )
        .add_geometry()
        .write_to(
            table_name=output_table_name,
            write_mode="overwrite"
        )
    )
