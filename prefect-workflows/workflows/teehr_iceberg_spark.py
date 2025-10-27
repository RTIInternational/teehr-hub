import time
from prefect import flow
import os

from simple_spark_helper import create_spark_session

@flow(flow_run_name="test-iceberg", log_prints=True)
def check() -> None:
    """Create Spark session with 2 executors for testing."""
    print("🚀 Starting Spark session...")
    
    spark = create_spark_session(
        app_name="spark",
        executor_instances=1,
        executor_memory="1g",
        executor_cores=1,
        driver_memory="1g"
    )

    # Check if session was created successfully
    if spark is None:
        print("❌ Failed to create Spark session!")
        raise RuntimeError("create_spark_session returned None")
    
    iceberg_catalog_uri = os.environ.get("ICEBERG_CATALOG_URI")
    print(f"ℹ️ Using Iceberg catalog URI: {iceberg_catalog_uri}")

    iceberg_warehouse = os.environ.get("ICEBERG_CATALOG_WAREHOUSE")
    print(f"ℹ️ Using Iceberg warehouse: {iceberg_warehouse}")

    # Test Iceberg connectivity
    spark.sql("USE iceberg;")

    spark.sql("SHOW NAMESPACES").show()

    spark.sql("SHOW TABLES IN iceberg.teehr").show()

    spark.sql("SELECT * FROM iceberg.teehr.sample").show()
    
    # Keep session alive for a bit to see it working
    print("⏰ Keeping session alive for 30 seconds...")
    time.sleep(30)
    
    print("🛑 Stopping Spark session...")
    spark.stop()
    print("✅ Spark session stopped successfully!")