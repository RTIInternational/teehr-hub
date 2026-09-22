import logging
from typing import Union
from pathlib import Path

from prefect.cache_policies import NO_CACHE
from prefect import task, flow, get_run_logger

from pyspark.sql import DataFrame as SparkDataFrame

import teehr
from teehr.querying.utils import join_geometry
from workflows.utils.common_utils import initialize_evaluation, set_table_properties
from data_utils import write_to_warehouse

logging.getLogger("teehr").setLevel(logging.INFO)

BY_LOCATION_TABLE_NAME = "configurations_by_location"
SUMMARY_TABLE_NAME = "configurations_summary"

# group_by / metrics become Iceberg table properties. The API reads them to
# decide which columns are filterable dimensions and which are values, so
# these lists are the contract between the warehouse and the OGC endpoints.
# 'name' and 'geometry' belong to neither list by convention.
BY_LOCATION_GROUP_BY = [
    "primary_location_id",
    "configuration_name",
    "variable_name",
    "unit_name",
]
BY_LOCATION_METRICS = [
    "min_reference_time",
    "max_reference_time",
    "min_value_time",
    "max_value_time",
    "num_members",
]
BY_LOCATION_DESCRIPTION = (
    "Configurations, variables and units available at each primary location, "
    "with timeseries time ranges and ensemble member counts"
)

SUMMARY_GROUP_BY = [
    "configuration_name",
    "variable_name",
    "unit_name",
    "timeseries_type",
]
SUMMARY_METRICS = [
    "min_reference_time",
    "max_reference_time",
    "min_value_time",
    "max_value_time",
    "num_locations",
    "description",
]
SUMMARY_DESCRIPTION = (
    "Per-configuration summary of available timeseries: variables, units, "
    "time ranges and location counts"
)

LOCATIONS_TABLE_NAME = "locations_with_attributes"

# The attribute columns are discovered from the data rather than listed here,
# and go in 'metrics': they are values of a location, not dimensions. Keeping
# them out of 'group_by' also holds the API's ORDER BY to two columns while
# still listing every attribute in /queryables for column discovery.
LOCATIONS_GROUP_BY = [
    "location_id",
    "name",
]
LOCATIONS_DESCRIPTION = (
    "One row per location with its attributes pivoted into columns"
)


@task(cache_policy=NO_CACHE)
def summarize_primary_locations(
    ev: teehr.Evaluation
) -> SparkDataFrame:
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
) -> SparkDataFrame:
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


@task(cache_policy=NO_CACHE)
def summarize_configurations(
    ev: teehr.Evaluation,
    by_location_sdf: SparkDataFrame
) -> SparkDataFrame:
    """Roll the per-location summary up to one row per configuration.

    Derived from the pre-geometry by-location frame so that num_locations counts
    every location with timeseries, not only those carrying geometry.
    """
    logger = get_run_logger()
    logger.info(
        "Rolling the location summary up to one row per configuration..."
    )
    by_location_sdf.createOrReplaceTempView("by_location")
    return ev.spark.sql("""
        WITH agg AS (
            SELECT
                configuration_name,
                variable_name,
                unit_name,
                MIN(min_reference_time) AS min_reference_time,
                MAX(max_reference_time) AS max_reference_time,
                MIN(min_value_time)     AS min_value_time,
                MAX(max_value_time)     AS max_value_time,
                COUNT(DISTINCT primary_location_id) AS num_locations
            FROM by_location
            GROUP BY configuration_name, variable_name, unit_name
        )
        SELECT
            agg.*,
            c.description,
            c.timeseries_type
        FROM agg
        JOIN iceberg.teehr.configurations c
            ON c.name = agg.configuration_name
    """)


@task(cache_policy=NO_CACHE)
def summarize_locations_with_attributes(
    ev: teehr.Evaluation
) -> SparkDataFrame:
    """Pivot location attributes into one row per location.

    location_attributes_view() does the long-to-wide pivot; the join adds
    'name' and is a LEFT join so locations without attributes still appear.
    """
    logger = get_run_logger()
    logger.info("Pivoting location attributes into a spark dataframe...")
    attributes_sdf = ev.location_attributes_view().to_sdf()
    locations_sdf = ev.locations.to_sdf().selectExpr("id AS location_id", "name")
    return locations_sdf.join(attributes_sdf, on="location_id", how="left")


@task(cache_policy=NO_CACHE)
def add_location_geometry(
    ev: teehr.Evaluation,
    by_location_sdf: SparkDataFrame
) -> SparkDataFrame:
    """Join 'name' and 'geometry' onto the per-location summary.

    join_geometry joins inner, and locations.geometry is nullable, so rows
    without a mappable location drop out here -- they could not be drawn or
    clicked through on the map anyway.
    """
    logger = get_run_logger()
    logger.info("Joining location geometry onto the location summary...")
    return join_geometry(
        by_location_sdf, ev.locations.to_sdf()
    ).filter("geometry IS NOT NULL")


@flow(
    flow_run_name="update-data-management-tables",
    timeout_seconds=60 * 60
)
def update_data_management_tables(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 48,
    executor_cores: int = 4,
    executor_memory: str = "32g",
) -> None:
    """Create the tables behind the data management dashboard.

    Builds 'configurations_by_location' and its rollup 'configurations_summary'
    from a single scan of the timeseries tables, plus 'locations_with_attributes'
    from the pivoted location attributes.

    Each table declares its own filterable dimensions ('group_by') and value
    columns ('metrics') as Iceberg table properties, which is how the OGC API
    serves them through the generic /collections/{id}/items route with no
    per-table code.
    """
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )

    by_location_sdf = summarize_primary_locations(ev=ev).unionByName(
        summarize_secondary_locations(ev=ev)
    )

    configurations_summary_sdf = summarize_configurations(
        ev=ev,
        by_location_sdf=by_location_sdf
    )

    by_location_with_geometry_sdf = add_location_geometry(
        ev=ev,
        by_location_sdf=by_location_sdf
    )

    locations_with_attributes_sdf = summarize_locations_with_attributes(ev=ev)

    # create_or_replace (not overwrite) because the schema changes between
    # runs. Partitioned on configuration_name: the dashboard's hot query
    # filters on it, and that is the query carrying geometry for every row.
    write_to_warehouse(
        ev=ev,
        sdf=by_location_with_geometry_sdf,
        table_name=BY_LOCATION_TABLE_NAME,
        write_mode="create_or_replace",
        partition_by=["configuration_name"],
        write_ordered_by=BY_LOCATION_GROUP_BY
    )
    write_to_warehouse(
        ev=ev,
        sdf=configurations_summary_sdf,
        table_name=SUMMARY_TABLE_NAME,
        write_mode="create_or_replace",
        write_ordered_by=SUMMARY_GROUP_BY
    )
    # create_or_replace because the attribute set -- and therefore the schema
    # -- changes as attributes are added to the warehouse.
    write_to_warehouse(
        ev=ev,
        sdf=locations_with_attributes_sdf,
        table_name=LOCATIONS_TABLE_NAME,
        write_mode="create_or_replace",
        write_ordered_by=["location_id"]
    )

    # Must run after the writes: create_or_replace drops the table, taking any
    # previously set properties with it.
    set_table_properties(
        ev=ev,
        table_name=BY_LOCATION_TABLE_NAME,
        properties={
            "description": BY_LOCATION_DESCRIPTION,
            "group_by": ", ".join(BY_LOCATION_GROUP_BY),
            "metrics": ", ".join(BY_LOCATION_METRICS),
        }
    )
    set_table_properties(
        ev=ev,
        table_name=SUMMARY_TABLE_NAME,
        properties={
            "description": SUMMARY_DESCRIPTION,
            "group_by": ", ".join(SUMMARY_GROUP_BY),
            "metrics": ", ".join(SUMMARY_METRICS),
        }
    )

    # Attribute columns are whatever the pivot produced.
    locations_metrics = [
        column for column in locations_with_attributes_sdf.columns
        if column not in LOCATIONS_GROUP_BY
    ]
    locations_properties = {
        "description": LOCATIONS_DESCRIPTION,
        "group_by": ", ".join(LOCATIONS_GROUP_BY),
    }
    if locations_metrics:
        locations_properties["metrics"] = ", ".join(locations_metrics)
    set_table_properties(
        ev=ev,
        table_name=LOCATIONS_TABLE_NAME,
        properties=locations_properties
    )
