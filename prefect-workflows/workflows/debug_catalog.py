"""Debug workflow to check Iceberg catalog configuration."""
import os
from prefect import flow, get_run_logger


@flow(
    flow_run_name="debug-catalog-config",
    timeout_seconds=60 * 10
)
def debug_catalog_config():
    """Debug the Iceberg catalog configuration."""
    logger = get_run_logger()

    # Check environment variables
    logger.info("=== Environment Variables ===")
    env_vars = [
        "REMOTE_CATALOG_REST_URI",
        "REMOTE_CATALOG_TYPE",
        "REMOTE_WAREHOUSE_S3_PATH",
        "REMOTE_CATALOG_S3_ENDPOINT",
        "REMOTE_CATALOG_S3_PATH_STYLE_ACCESS",
        "IN_CLUSTER",
        "AWS_REGION",
        "TEEHR_NAMESPACE",
        "TEEHR_SPARK_IMAGE",
    ]
    for var in env_vars:
        value = os.environ.get(var, "NOT SET")
        logger.info(f"{var}: {value}")

    # Test Spark session creation
    logger.info("\n=== Creating Spark Session ===")
    from teehr.evaluation.spark_session_utils import create_spark_session
    import teehr.const as const

    logger.info(f"const.REMOTE_CATALOG_REST_URI: {const.REMOTE_CATALOG_REST_URI}")
    logger.info(f"const.REMOTE_CATALOG_TYPE: {const.REMOTE_CATALOG_TYPE}")
    logger.info(f"const.REMOTE_WAREHOUSE_S3_PATH: {const.REMOTE_WAREHOUSE_S3_PATH}")

    spark = create_spark_session(
        start_spark_cluster=False,
        debug_config=True
    )

    # Check catalogs
    logger.info("\n=== Checking Catalogs ===")
    logger.info(f"Current catalog: {spark.catalog.currentCatalog()}")

    # List catalogs
    try:
        catalogs = spark.sql("SHOW CATALOGS").collect()
        logger.info(f"Available catalogs: {[c[0] for c in catalogs]}")
    except Exception as e:
        logger.warning(f"Could not list catalogs: {e}")

    # Check current namespace
    spark.catalog.setCurrentCatalog("iceberg")
    logger.info(f"Current catalog after set: {spark.catalog.currentCatalog()}")

    # Try to access units table
    logger.info("\n=== Testing Units Table Access ===")
    try:
        # Method 1: Direct SQL
        logger.info("Method 1: Direct SQL query")
        schema_df = spark.sql("DESCRIBE iceberg.teehr.units")
        logger.info(f"Units table schema columns: {schema_df.columns}")
        schema_rows = schema_df.collect()
        logger.info(f"Units table schema: {schema_rows}")

        data_df = spark.sql("SELECT * FROM iceberg.teehr.units")
        logger.info(f"Units table data columns: {data_df.columns}")
        data_rows = data_df.collect()
        logger.info(f"Units table data: {data_rows}")
    except Exception as e:
        logger.error(f"Error accessing units table via SQL: {e}")

    # Method 2: Via TEEHR Evaluation
    logger.info("\n=== Testing via TEEHR Evaluation ===")
    try:
        import teehr
        ev = teehr.Evaluation(
            spark=spark,
            dir_path="/data/temp_debug",
            create_dir=True
        )
        ev.set_active_catalog("remote")
        logger.info(f"Active catalog name: {ev.active_catalog.catalog_name}")
        logger.info(f"Active namespace: {ev.active_catalog.namespace_name}")

        # Try the units table
        units_sdf = ev.units.to_sdf()
        logger.info(f"Units SDF schema: {units_sdf.schema}")
        logger.info(f"Units SDF columns: {units_sdf.columns}")
        units_count = units_sdf.count()
        logger.info(f"Units count: {units_count}")

        if units_count > 0:
            units_sdf.show()
    except Exception as e:
        logger.error(f"Error accessing units via TEEHR: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Check Iceberg table metadata
    logger.info("\n=== Checking Iceberg Table Metadata ===")
    try:
        spark.sql("SELECT * FROM iceberg.teehr.units.history").show()
        spark.sql("SELECT * FROM iceberg.teehr.units.snapshots").show()
    except Exception as e:
        logger.warning(f"Could not get table metadata: {e}")

    logger.info("\n=== Debug Complete ===")
    return "Debug complete"


if __name__ == "__main__":
    debug_catalog_config()
