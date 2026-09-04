import logging
import time
from typing import Union
from pathlib import Path

from prefect.cache_policies import NO_CACHE
from prefect import task, flow, get_run_logger
from pyspark.sql import Row
from pyspark.sql import functions as F

from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)


def probe_executor_env(spark, expected_env_keys, partitions=8):
    """
    Returns one row per partition attempt with only booleans + executor identity.
    Never returns secret values.
    """
    keys = list(expected_env_keys)

    def _probe_partition(it):
        import os
        import socket
        # Force execution of partition iterator so Spark doesn't prune the task.
        _ = list(it)
        result = {
            "executor_host": socket.gethostname(),
            "pid_present": os.getpid() > 0,
        }
        for k in keys:
            result[f"has_{k}"] = bool(os.environ.get(k))
        yield Row(**result)

    # Use enough partitions to spread across executors
    rdd = spark.sparkContext.parallelize(range(partitions), partitions)
    rows = rdd.mapPartitions(_probe_partition).collect()
    return rows


@flow(
    flow_run_name="distributed-rw-auth-test",
    timeout_seconds=60 * 60,
    log_prints=True
)
def distributed_rw_auth(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = True,
    executor_instances: int = 1,
    executor_cores: int = 1,
    executor_memory: str = "1g"
) -> None:
    """Distributed read/write authorization test for Polaris/Iceberg."""
    
    logger = get_run_logger()
    logger.info(
        f"Running distributed read/write auth test with temp_dir_path='{temp_dir_path}'..."
    )
    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        executor_instances=executor_instances,
        executor_cores=executor_cores,
        executor_memory=executor_memory,
        update_configs={"spark.kubernetes.executor.node.selector.teehr-hub/nodegroup-name": "spark-r5-4xlarge"}
    )
    spark = ev.spark


    logger.info(
        f"POLARIS_OAUTH2_SERVER_URI={spark.conf.get('spark.executorEnv.POLARIS_OAUTH2_SERVER_URI')}, "
    )

    logger.info(
        f"POLARIS_CLIENT_ID={spark.conf.get('spark.executorEnv.POLARIS_CLIENT_ID')}, "
    )

    logger.info(
        f"POLARIS_CLIENT_SECRET={spark.conf.get('spark.executorEnv.POLARIS_CLIENT_SECRET')}"
    )


    expected = [
        "POLARIS_OAUTH2_SERVER_URI",
        "POLARIS_CLIENT_ID",
        "POLARIS_CLIENT_SECRET",
    ]
    rows = probe_executor_env(spark, expected, partitions=12)
    for r in rows:
        print(r.asDict())


    

    catalog = "iceberg"
    namespace = "teehr"
    table = f"executor_probe_{int(time.time())}"
    full_table = f"{catalog}.{namespace}.{table}"

    # 1) Build distributed data (force executor work via repartition)
    n = 200_000
    parts = 12
    df = (
        spark.range(0, n)
        .repartition(parts)
        .withColumn("grp", (F.col("id") % 17).cast("int"))
        .withColumn("payload", F.concat(F.lit("v-"), F.col("id").cast("string")))
    )

    # Optional: materialize first to ensure tasks run
    print("input_count:", df.count())

    # 2) Real distributed WRITE to Polaris/Iceberg
    df.writeTo(full_table).using("iceberg").create()

    # 3) Real distributed READ from Polaris/Iceberg
    read_df = spark.read.table(full_table).repartition(parts)
    print("table_count:", read_df.count())

    # 4) A distributed aggregate to exercise more executor paths
    agg = (
        read_df.groupBy("grp")
        .count()
        .orderBy("grp")
    )
    agg.show(20, truncate=False)

    # 5) Cleanup
    spark.sql(f"DROP TABLE {full_table}")
    print("dropped:", full_table)