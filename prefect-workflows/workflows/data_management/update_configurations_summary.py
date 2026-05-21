from pathlib import Path
from typing import Union
import logging

from prefect.cache_policies import NO_CACHE
from prefect import task, flow, get_run_logger

import teehr
from workflows.utils.common_utils import initialize_evaluation
from data_utils import write_to_warehouse

logging.getLogger("teehr").setLevel(logging.INFO)

GROUPBY = ["configuration_name", "variable_name"]
OUTPUT_TABLE_NAME = "configurations_summary"


@task(cache_policy=NO_CACHE)
def summarize_configurations_by_timeseries_type(
    ev: teehr.Evaluation,
    timeseries_type: str
) -> None:
    """Summarize configurations by timeseries type (primary vs secondary)."""
    logger = get_run_logger()
    group_by_clause = ", ".join([f"{c}" for c in GROUPBY])

    member_cols = ""
    if timeseries_type == "secondary":
        member_cols = """
            ,
            COUNT(DISTINCT member)  AS n_members,
            COLLECT_SET(member)     AS members
        """
    else:
        member_cols = """
            ,
            CAST(NULL AS BIGINT)    AS n_members,
            CAST(NULL AS ARRAY<STRING>) AS members
        """
    logger.info(
        f"Summarizing configurations by {timeseries_type} timeseries into a spark dataframe..."
    )
    return ev.spark.sql(f"""
        WITH agg AS (
            SELECT
                configuration_name,
                variable_name,
                unit_name,
                MIN(reference_time)             AS min_reference_time,
                MAX(reference_time)             AS max_reference_time,
                MIN(value_time)                 AS min_value_time,
                MAX(value_time)                 AS max_value_time,
                approx_count_distinct(location_id)    AS n_locations
                {member_cols}
            FROM iceberg.teehr.{timeseries_type}_timeseries
            GROUP BY unit_name, {group_by_clause}
        )
        SELECT
            agg.*,
            c.description,
            c.timeseries_type,
            SPLIT(agg.configuration_name, '_')[0] AS location_id_prefix
        FROM agg
        JOIN iceberg.teehr.configurations c
            ON c.name = agg.configuration_name
    """)


@flow(
    flow_run_name="update-configurations-summary-table",
    timeout_seconds=60 * 60
)
def update_configurations_summary_table(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 48,
    executor_cores: int = 4,
    executor_memory: str = "32g"
) -> None:
    """Create the configurations summary table."""
    logger = get_run_logger()

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )

    logger.info("Summarizing configurations for each timeseries table...")
    primary_sdf = summarize_configurations_by_timeseries_type(
        ev=ev,
        timeseries_type="primary"
    )
    secondary_sdf = summarize_configurations_by_timeseries_type(
        ev=ev,
        timeseries_type="secondary"
    )
    result_sdf = primary_sdf.unionByName(secondary_sdf)

    write_to_warehouse(
        ev=ev,
        sdf=result_sdf,
        table_name=OUTPUT_TABLE_NAME
    )