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

    # NEW: Simulate what _enforce_foreign_keys does
    logger.info("\n=== Simulating Foreign Key Enforcement (the actual failing code path) ===")
    try:
        import teehr
        ev2 = teehr.Evaluation(
            spark=spark,
            dir_path="/data/temp_debug2",
            create_dir=True
        )
        ev2.set_active_catalog("remote")

        # Step 1: Create a temp view like _enforce_foreign_keys does
        logger.info("Step 1: Getting units SDF via ev.units.to_sdf()")
        units_sdf_for_view = ev2.units.to_sdf()
        logger.info(f"  Schema: {units_sdf_for_view.schema}")
        logger.info(f"  Columns: {units_sdf_for_view.columns}")

        # Step 2: Create temp view
        logger.info("Step 2: Creating temp view 'units'")
        units_sdf_for_view.createOrReplaceTempView("units")

        # Step 3: Check the temp view schema
        logger.info("Step 3: Checking temp view schema")
        temp_view_df = spark.sql("SELECT * FROM units")
        logger.info(f"  Temp view columns: {temp_view_df.columns}")
        logger.info(f"  Temp view schema: {temp_view_df.schema}")

        # Step 4: Try the actual foreign key SQL pattern
        logger.info("Step 4: Testing the exact SQL pattern used in _enforce_foreign_keys")

        # Create a mock temp_table with unit_name
        from pyspark.sql import Row
        mock_data = [Row(unit_name="m^3/s", value=1.0)]
        mock_df = spark.createDataFrame(mock_data)
        mock_df.createOrReplaceTempView("temp_table")

        fk_sql = """
            SELECT t.* from temp_table t
            LEFT ANTI JOIN units d
            ON t.unit_name = d.name
        """
        logger.info(f"  Running SQL: {fk_sql}")

        result_sdf = spark.sql(fk_sql)
        logger.info(f"  Result columns: {result_sdf.columns}")
        logger.info(f"  Result count: {result_sdf.count()}")
        logger.info("  SUCCESS - Foreign key SQL pattern works!")

        # Step 5: Now test via ev.sql() which is what the actual code uses
        logger.info("Step 5: Testing via ev.sql() method")
        spark.catalog.dropTempView("units")  # Clear the temp view first

        # This is what _enforce_foreign_keys actually calls
        result_via_ev_sql = ev2.sql(
            query=fk_sql,
            create_temp_views=["units"]
        )
        logger.info(f"  Result via ev.sql() columns: {result_via_ev_sql.columns}")
        logger.info(f"  Result via ev.sql() count: {result_via_ev_sql.count()}")
        logger.info("  SUCCESS - ev.sql() pattern works!")

    except Exception as e:
        logger.error(f"ERROR in foreign key simulation: {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info("\n=== Debug Complete ===")
    return "Debug complete"


if __name__ == "__main__":
    debug_catalog_config()
