import logging
from typing import Union
from pathlib import Path

from prefect.cache_policies import NO_CACHE
from prefect import task, flow, get_run_logger

import teehr
from workflows.utils.common_utils import initialize_evaluation
from data_utils import write_to_warehouse

logging.getLogger("teehr").setLevel(logging.INFO)

OUTPUT_TABLE_NAME = "configuration_completeness"


@task(cache_policy=NO_CACHE)
def calculate_primary_completeness(
    ev: teehr.Evaluation,
    period: str = "month",
    spatial_agg: str = "huc6"
) -> None:
    """Summarize primary locations."""
    logger = get_run_logger()
    logger.info(
        f"Calculating completeness with period='{period}' and spatial_agg='{spatial_agg}'..."
    )
    # THIS IGNORES FORCING BY DEFAULT (only 'usgs-' locations)
    ptv_sdf = ev.primary_timeseries_view(
        add_attrs=True,
        attr_list=[spatial_agg]
    ).to_sdf()
    ptv_sdf.createOrReplaceTempView("ts")

    return ev.spark.sql(f"""
        WITH period_counts AS (
            SELECT
                CONCAT('{spatial_agg}-', {spatial_agg}) AS spatial_aggregate,
                {spatial_agg} AS spatial_agg_id,
                configuration_name,
                variable_name,
                DATE_TRUNC('{period}', value_time) AS period,
                COUNT(*) AS actual_count
            FROM ts
            GROUP BY {spatial_agg}, configuration_name, variable_name,
                    DATE_TRUNC('{period}', value_time)
        ),
        with_expected AS (
            SELECT
                spatial_aggregate,
                configuration_name,
                variable_name,
                period,
                actual_count,
                MAX(actual_count) OVER (PARTITION BY spatial_agg_id, configuration_name, variable_name) AS expected_count
            FROM period_counts
        )
        SELECT
            *,
            LEAST(actual_count / expected_count * 100.0, 100.0) AS completeness
        FROM with_expected
    """)


@flow(
    flow_run_name="update-completeness-heatmap-table",
    timeout_seconds=60 * 60
)
def update_completeness_summary_table(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 32,
    executor_cores: int = 4,
    executor_memory: str = "32g",
    period: str = "month",
    spatial_agg: str = "huc6"
) -> None:
    """Update the completeness summary table.

    Note: This currently only calculates completeness for primary locations,
    and ignores forcing timeseries due to the attribute join.
    """
    logger = get_run_logger()
    logger.info(
        f"Updating completeness summary table with period='{period}' and spatial_agg='{spatial_agg}'..."
    )
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )
    completeness_sdf = calculate_primary_completeness(ev, period, spatial_agg)
    write_to_warehouse(
        ev=ev,
        sdf=completeness_sdf,
        table_name=OUTPUT_TABLE_NAME
    )