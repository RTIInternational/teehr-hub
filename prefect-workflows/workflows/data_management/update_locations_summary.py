import logging
from typing import Union
from pathlib import Path

from prefect.cache_policies import NO_CACHE
from prefect import task, flow, get_run_logger

import teehr
from workflows.utils.common_utils import initialize_evaluation
from data_utils import write_to_warehouse

logging.getLogger("teehr").setLevel(logging.INFO)

OUTPUT_TABLE_NAME = "configurations_by_location"


@task(cache_policy=NO_CACHE)
def summarize_primary_locations(
    ev: teehr.Evaluation
) -> None:
    """Summarize primary locations."""
    logger = get_run_logger()
    logger.info(
        "Summarizing primary locations into a spark dataframe..."
    )
    return ev.spark.sql("""
        SELECT
            location_id as primary_location_id,
            configuration_name,
            variable_name,
            unit_name,
            MIN(reference_time) AS min_reference_time,
            MAX(reference_time) AS max_reference_time,
            MIN(value_time)     AS min_value_time,
            MAX(value_time)     AS max_value_time,
            CAST(NULL AS BIGINT) AS num_members
        FROM iceberg.teehr.primary_timeseries
        GROUP BY primary_location_id, configuration_name, variable_name, unit_name
    """)


@task(cache_policy=NO_CACHE)
def summarize_secondary_locations(
    ev: teehr.Evaluation
) -> None:
    """Summarize secondary locations."""
    logger = get_run_logger()
    logger.info(
        "Summarizing secondary locations into a spark dataframe..."
    )
    return ev.spark.sql("""
        SELECT
            cf.primary_location_id,
            st.configuration_name,
            st.variable_name,
            st.unit_name,
            MIN(st.reference_time) AS min_reference_time,
            MAX(st.reference_time) AS max_reference_time,
            MIN(st.value_time)     AS min_value_time,
            MAX(st.value_time)     AS max_value_time,
            COUNT(DISTINCT st.member) AS num_members
        FROM iceberg.teehr.secondary_timeseries st
        JOIN iceberg.teehr.location_crosswalks cf
            ON cf.secondary_location_id = st.location_id
        GROUP BY cf.primary_location_id, st.configuration_name, st.variable_name, st.unit_name
    """)


@flow(
    flow_run_name="update-locations-summary-table",
    timeout_seconds=60 * 60
)
def update_locations_summary_table(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 48,
    executor_cores: int = 4,
    executor_memory: str = "32g",
) -> None:
    """Create the locations summary table."""
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )

    primary_locations_summary_sdf = summarize_primary_locations(ev=ev)
    secondary_locations_summary_sdf = summarize_secondary_locations(ev=ev)

    result_sdf = primary_locations_summary_sdf.unionByName(secondary_locations_summary_sdf)

    write_to_warehouse(
        ev=ev,
        sdf=result_sdf,
        table_name=OUTPUT_TABLE_NAME
    )