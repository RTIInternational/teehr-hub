from pathlib import Path
from typing import Union
import logging

from prefect import flow, get_run_logger

from teehr import DeterministicMetrics as dm
from teehr import RowLevelCalculatedFields as rcf
from utils.common_utils import initialize_evaluation
from update_joined_forecasts import JOINED_FORECAST_TABLE_NAME

logging.getLogger("teehr").setLevel(logging.INFO)

METRICS_TABLE_NAME = "forecast_metrics_by_location"


@flow(
    flow_run_name="update-forecast-metrics-table",
    timeout_seconds=60 * 60,
    retries=2
)
def update_forecast_metrics_table(
    dir_path: Union[str, Path]
) -> None:
    """Create the forecast metrics table

    Notes
    -----
    - This requires the joined forecast table to be created first using
      the `update_joined_forecast_table` flow.
    - Currently, the forecast metrics table is re-created each time.
    """
    logger = get_run_logger()

    ev = initialize_evaluation(dir_path=dir_path)

    logger.info("Creating forecast metrics table...")

    sdf = (
        ev
        .metrics(table_name=JOINED_FORECAST_TABLE_NAME).
        add_calculated_fields([
            rcf.ForecastLeadTime()
        ])
        .query(
            include_metrics=[
                dm.PearsonCorrelation(),
                dm.RelativeBias(),
                dm.NashSutcliffeEfficiency(),
                dm.KlingGuptaEfficiency()
            ],
            group_by=[
                "primary_location_id",
                "configuration_name",
                "forecast_lead_time"
            ],
        ).to_sdf()
    )
    sdf.createTempView("metrics")

    sdf = ev.spark.sql("""
        SELECT m.*, l.*
        FROM metrics m
        JOIN iceberg.teehr.locations l
        ON l.id = m.primary_location_id
    """)
    sdf = sdf.drop("id")

    ev.write.to_warehouse(
        source_data=sdf,
        table_name=METRICS_TABLE_NAME,
        write_mode="create_or_replace"
    )

    logger.info("Forecast metrics table created.")
