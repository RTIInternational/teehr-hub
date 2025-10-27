from prefect import flow

from simple_spark_helper import create_spark_session

@flow(flow_run_name="create", log_prints=True)
def create() -> None:
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
    
    print("⏳ Waiting for Spark session to be ready...")
    
    # Wait for Spark context to be initialized
    import time
    max_wait = 60  # seconds
    start_time = time.time()
    
    # Check if sparkContext exists and is initialized
    while spark.sparkContext is None or not hasattr(spark.sparkContext, '_jsc') or spark.sparkContext._jsc is None:
        if time.time() - start_time > max_wait:
            print("❌ Timeout waiting for Spark session")
            raise TimeoutError("Spark session failed to initialize within 60 seconds")
        print("🔄 Still waiting for Spark context...")
        time.sleep(2)
    
    # Test basic Spark functionality
    print("🧪 Testing Spark connectivity...")
    try:
        # Simple test - create a small RDD
        test_data = spark.sparkContext.parallelize([1, 2, 3, 4, 5])
        result = test_data.sum()
        print(f"✅ Spark test successful! Sum result: {result}")
    except Exception as e:
        print(f"❌ Spark test failed: {e}")
        raise
    
    print("🎉 Spark session ready and validated!")
    print(f"📊 Spark UI: {spark.sparkContext.uiWebUrl}")
    print(f"🎯 Application ID: {spark.sparkContext.applicationId}")
    
    # Keep session alive for a bit to see it working
    print("⏰ Keeping session alive for 30 seconds...")
    time.sleep(30)
    
    print("🛑 Stopping Spark session...")
    spark.stop()
    print("✅ Spark session stopped successfully!")