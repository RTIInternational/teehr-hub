import logging
from functools import reduce
from pathlib import Path

import pyspark.sql.functions as F
import teehr
from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE
from pyspark.sql import DataFrame as SparkDataFrame
from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)

COMBINATIONS_TABLE_NAME = "queryable_combinations"
COMBINATIONS_TABLE = f"iceberg.teehr.{COMBINATIONS_TABLE_NAME}"
COMBINATIONS_DESCRIPTION = (
    "Distinct group_by dimension combinations of each table that declares a "
    "group_by property, used by the API to serve queryable values without "
    "scanning the source table"
)

# Location ids are too high-cardinality to be dropdown filters, and
# name/geometry are location attributes rather than dimensions.
EXCLUDED_DIMENSIONS = {
    "primary_location_id",
    "secondary_location_id",
    "location_id",
    "name",
    "geometry",
}


@task(cache_policy=NO_CACHE)
def create_combinations_table(ev: teehr.Evaluation) -> None:
    """Create the combinations table if it does not exist."""
    ev.spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {COMBINATIONS_TABLE} (
            source_table STRING,
            source_snapshot_id BIGINT,
            dimensions MAP<STRING, STRING>,
            computed_at TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (source_table)
        TBLPROPERTIES (
            'description' = '{COMBINATIONS_DESCRIPTION}',
            'format-version' = '2'
        )
    """)


@task(cache_policy=NO_CACHE)
def get_source_tables(ev: teehr.Evaluation) -> dict[str, dict]:
    """Current snapshot and cacheable dimensions of each group_by table."""
    logger = get_run_logger()
    sources = {}
    for table_name in ev.list_tables()["name"].tolist():
        if table_name == COMBINATIONS_TABLE_NAME:
            continue
        properties = {
            row["key"]: row["value"]
            for row in ev.spark.sql(
                f"SHOW TBLPROPERTIES iceberg.teehr.{table_name}"
            ).collect()
        }
        group_by = properties.get("group_by")
        snapshot_id = properties.get("current-snapshot-id", "none")
        if not group_by or snapshot_id == "none":
            continue
        dimensions = sorted(
            column
            for column in (c.strip() for c in group_by.split(","))
            if column and column not in EXCLUDED_DIMENSIONS
        )
        if dimensions:
            sources[table_name] = {
                "snapshot_id": int(snapshot_id),
                "dimensions": dimensions,
            }
    logger.info(f"Found {len(sources)} source tables: {sorted(sources)}")
    return sources


@task(cache_policy=NO_CACHE)
def get_cached_sources(ev: teehr.Evaluation) -> dict[str, dict]:
    """Snapshot and dimensions each source was last computed from."""
    rows = ev.spark.sql(f"""
        SELECT
            source_table,
            first(source_snapshot_id) AS snapshot_id,
            first(array_sort(map_keys(dimensions))) AS dimensions
        FROM {COMBINATIONS_TABLE}
        GROUP BY source_table
    """).collect()
    return {
        row["source_table"]: {
            "snapshot_id": row["snapshot_id"],
            "dimensions": list(row["dimensions"]),
        }
        for row in rows
    }


@task(cache_policy=NO_CACHE)
def compute_combinations(
    ev: teehr.Evaluation,
    table_name: str,
    snapshot_id: int,
    dimensions: list[str],
) -> SparkDataFrame:
    """Distinct dimension combinations of a source table."""
    logger = get_run_logger()
    logger.info(
        f"Computing combinations of {table_name} at snapshot {snapshot_id} "
        f"over {dimensions}"
    )
    columns = ", ".join(f"`{d}`" for d in dimensions)
    # Pinned so the stored snapshot id describes exactly the data scanned,
    # even if the source is written to mid-run.
    distinct_sdf = ev.spark.sql(f"""
        SELECT DISTINCT {columns}
        FROM iceberg.teehr.{table_name} VERSION AS OF {snapshot_id}
    """)
    map_entries = []
    for d in dimensions:
        map_entries += [F.lit(d), F.col(f"`{d}`").cast("string")]
    return distinct_sdf.select(
        F.lit(table_name).alias("source_table"),
        F.lit(snapshot_id).cast("bigint").alias("source_snapshot_id"),
        F.create_map(*map_entries).alias("dimensions"),
        F.current_timestamp().alias("computed_at"),
    )


@flow(flow_run_name="update-queryable-combinations", timeout_seconds=60 * 60)
def update_queryable_combinations(
    temp_dir_path: str | Path,
    start_spark_cluster: bool = False,
    executor_instances: int = 2,
    executor_cores: int = 4,
    executor_memory: str = "16g",
) -> None:
    """Refresh the precomputed queryable value combinations.

    Recomputes only sources whose snapshot or dimensions changed since the
    last run, and drops sources that no longer exist or declare group_by.
    """
    logger = get_run_logger()

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
    )

    create_combinations_table(ev=ev)
    sources = get_source_tables(ev=ev)
    cached = get_cached_sources(ev=ev)

    changed = sorted(
        table_name
        for table_name, source in sources.items()
        if cached.get(table_name) != source
    )
    removed = sorted(set(cached) - set(sources))
    logger.info(f"Changed sources: {changed}. Removed sources: {removed}")

    if not changed and not removed:
        return

    empty_sdf = ev.spark.createDataFrame([], ev.spark.table(COMBINATIONS_TABLE).schema)
    combinations_sdf = reduce(
        SparkDataFrame.unionByName,
        [
            compute_combinations(
                ev=ev,
                table_name=table_name,
                snapshot_id=sources[table_name]["snapshot_id"],
                dimensions=sources[table_name]["dimensions"],
            )
            for table_name in changed
        ],
        empty_sdf,
    )

    # One commit replacing exactly the affected partitions, so the API never
    # sees a source half-updated, and an empty result still clears the
    # partition (overwritePartitions would leave it untouched).
    combinations_sdf.writeTo(COMBINATIONS_TABLE).overwrite(
        F.col("source_table").isin(changed + removed)
    )
    logger.info(f"Wrote combinations for {changed}; removed {removed}")
