"""
Simple Spark Kubernetes Helper for TEEHR Hub
Works with the existing JupyterHub setup without complex RBAC configurations.
"""

import os
import socket
from pyspark.sql import SparkSession
from pyspark import SparkConf


SCALA_VERSION = "2.13"
PYSPARK_VERSION = "4.0"
ICEBERG_VERSION = "1.10.0"
SEDONA_VERSION = "1.8.0"

REMOTE_CATALOG_NAME = "iceberg"
REMOTE_CATALOG_TYPE = "rest"

CATALOG_REST_URI = "http://dev-teehr-sys-iceberg-alb-2105268770.us-east-2.elb.amazonaws.com"
WAREHOUSE_S3_PATH = "s3://dev-teehr-sys-iceberg-warehouse/warehouse/"


def create_spark_session(
    app_name="spark-k8s-app",
    executor_instances=4,  # Increased from 2
    executor_memory="2g",  # Increased from 1g  
    executor_cores=2,      # Increased from 1
    driver_memory="2g",    # Increased from 1g
    driver_max_result_size="1g",
    container_image="935462133478.dkr.ecr.us-east-2.amazonaws.com/teehr-spark/teehr-spark-executor:latest",
    spark_namespace="spark"
):
    """
    Create a Spark session configured for Kubernetes execution.
    
    This version runs the driver locally in the Jupyter pod and launches
    executors in the specified Kubernetes namespace.
    """
    
    # Default container image - use the same image as the current pod
    if container_image is None:
        container_image = "935462133478.dkr.ecr.us-east-2.amazonaws.com/teehr-spark/teehr-spark-executor:latest"
    
    # Get Kubernetes API server - use HTTPS port specifically
    k8s_host = os.environ.get('KUBERNETES_SERVICE_HOST', 'kubernetes.default.svc.cluster.local')
    k8s_port_https = os.environ.get('KUBERNETES_SERVICE_PORT_HTTPS', '443')
    k8s_api_server = f"https://{k8s_host}:{k8s_port_https}"
    
    # Detect current namespace if running in a pod
    current_namespace = "default"
    namespace_file = "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
    if os.path.exists(namespace_file):
        with open(namespace_file, 'r') as f:
            current_namespace = f.read().strip()
    
    print(f"🔍 Connecting to Kubernetes API: {k8s_api_server}")
    print(f"🚀 Creating Spark session: {app_name}")
    print(f"📦 Using container image: {container_image}")
    print(f"🏠 Current namespace: {current_namespace}")
    print(f"🎯 Executor namespace: {spark_namespace}")
    print(f"🔐 Driver service account: default (in {current_namespace})")
    print(f"🔐 Executor service account: spark (in {spark_namespace})")
    
    # Create Spark configuration
    conf = SparkConf().setAppName(app_name).setMaster(f"k8s://{k8s_api_server}")

    # Basic Kubernetes settings. 
    conf.set("spark.kubernetes.container.image", container_image)
    conf.set("spark.kubernetes.container.image.pullPolicy", "Always")
    conf.set("spark.kubernetes.namespace", spark_namespace)
    conf.set("spark.kubernetes.authenticate.executor.serviceAccountName", "spark")

    # Executor settings
    conf.set("spark.executor.instances", str(executor_instances))
    conf.set("spark.executor.memory", executor_memory)
    conf.set("spark.executor.cores", str(executor_cores))

    # Driver settings
    conf.set("spark.driver.memory", driver_memory)
    conf.set("spark.driver.maxResultSize", driver_max_result_size)

    # Spark executor pod settings
    conf.set("spark.kubernetes.executor.node.selector.k8s.dask.org/node-purpose", "worker")
    conf.set("spark.kubernetes.executor.podTemplateFile", "executor-pod-template.yaml")
    conf.set("spark.kubernetes.executor.deleteOnTermination", "true")

    # UDF-specific optimizations that MUST be set at session creation
    conf.set("spark.python.worker.memory", "2g")  # Memory per Python worker
    conf.set("spark.python.worker.reuse", "true")  # Reuse Python workers
    conf.set("spark.executor.memoryFraction", "0.8")  # More memory for execution
    
    # Pandas UDF specific settings
    conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")  # Essential
    conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "5000")  # Smaller batches
    conf.set("spark.sql.execution.arrow.pyspark.fallback.enabled", "false")  # Force Arrow
    
    # Optimize shuffle partitions for UDFs (much lower)
    conf.set("spark.sql.shuffle.partitions", "8")  # Very low for UDF operations

    # Serialization
    conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer")

    # Authentication - use service account token if available
    token_file = "/var/run/secrets/kubernetes.io/serviceaccount/token"
    ca_file = "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt"
    
    if os.path.exists(token_file) and os.path.exists(ca_file):
        print("🔐 Using in-cluster authentication")
        conf.set("spark.kubernetes.authenticate.submission.oauthTokenFile", token_file)
        conf.set("spark.kubernetes.authenticate.submission.caCertFile", ca_file)
        conf.set("spark.kubernetes.authenticate.driver.oauthTokenFile", token_file)
        conf.set("spark.kubernetes.authenticate.executor.oauthTokenFile", token_file)
        
        # Critical: Set the CA cert file for SSL validation
        conf.set("spark.kubernetes.authenticate.caCertFile", ca_file)
    else:
        print("⚠️  No service account tokens found - may have authentication issues")
        print(f"   Checked: {token_file}")
        print(f"   Checked: {ca_file}")
    
    # Mount shared data volume in executors
    conf.set("spark.kubernetes.executor.volumes.persistentVolumeClaim.data-nfs.mount.path", "/data")
    conf.set("spark.kubernetes.executor.volumes.persistentVolumeClaim.data-nfs.options.claimName", "data-nfs")
    
    # Dynamic allocation
    conf.set("spark.dynamicAllocation.enabled", "true")
    conf.set("spark.dynamicAllocation.minExecutors", "1")
    conf.set("spark.dynamicAllocation.maxExecutors", "100")
    conf.set("spark.dynamicAllocation.initialExecutors", str(executor_instances))
    
    # Basic timeout configuration
    conf.set("spark.network.timeout", "300s")
    conf.set("spark.kubernetes.submission.connectionTimeout", "30000")
    conf.set("spark.kubernetes.submission.requestTimeout", "30000")
    
    # Performance optimizations
    conf.set("spark.sql.adaptive.enabled", "true")  # Enable adaptive query execution
    conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")  # Coalesce small partitions
    conf.set("spark.sql.adaptive.skewJoin.enabled", "true")  # Handle skewed joins
    conf.set("spark.sql.adaptive.localShuffleReader.enabled", "true")  # Optimize shuffle reads
    
    # Optimize parallelism for cluster size
    total_cores = executor_instances * executor_cores
    optimal_partitions = max(total_cores * 2, 8)  # At least 8, usually 2x cores
    conf.set("spark.sql.shuffle.partitions", str(optimal_partitions))  # Much lower than 200
    conf.set("spark.default.parallelism", str(total_cores * 2))
    
    # Memory and storage optimizations
    conf.set("spark.serializer.objectStreamReset", "100")
    conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")  # Use Arrow for pandas conversion
    conf.set("spark.sql.parquet.columnarReaderBatchSize", "4096")  # Optimize parquet reading
    
    # Iceberg-specific optimizations
    conf.set("spark.sql.iceberg.vectorization.enabled", "true")  # Enable Iceberg vectorization
    conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "128MB")  # Larger partition target
    conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "64MB")  # Coalesce small partitions
    
    # Reduce small file overhead
    conf.set("spark.sql.adaptive.coalescePartitions.parallelismFirst", "false")
    conf.set("spark.sql.adaptive.maxNumPostShufflePartitions", str(optimal_partitions))
    
    print(f"🎯 Optimized for {total_cores} total cores with {optimal_partitions} shuffle partitions")
    
    # Driver binding configuration - use pod IP for Kubernetes
    conf.set("spark.driver.bindAddress", "0.0.0.0")
    conf.set("spark.driver.port", "0")  # Let Spark choose an available port

    # # Setup Iceberg (commented because of memory issues and not needed right now)
    # conf.set(
    #     "spark.jars.packages",
    #     f"org.apache.sedona:sedona-spark-shaded-{PYSPARK_VERSION}_{SCALA_VERSION}:{SEDONA_VERSION},"
    #     f"org.apache.iceberg:iceberg-spark-runtime-{PYSPARK_VERSION}_{SCALA_VERSION}:{ICEBERG_VERSION},"
    #     "org.datasyslab:geotools-wrapper:1.8.0-33.1,"  # for raster ops
    #     f"org.apache.iceberg:iceberg-spark-extensions-{PYSPARK_VERSION}_{SCALA_VERSION}:{ICEBERG_VERSION},"
    #     "org.apache.hadoop:hadoop-aws:3.4.2,"  # SEEMS TO CAUSE HIGH MEMORY USAGE?
    #     "com.amazonaws:aws-java-sdk-bundle:1.12.791,"
    #     "org.slf4j:slf4j-simple:1.7.36"  # Add SLF4J simple binding to suppress warnings
    # )

    # # Iceberg extensions (enable iceberg-specific SQL commands such as time travel, merge-into, etc.)
    # conf.set("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")

    # # Remote catalog configuration
    # conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}", "org.apache.iceberg.spark.SparkCatalog")
    # conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.type", REMOTE_CATALOG_TYPE)
    # conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.uri", CATALOG_REST_URI)
    # conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.warehouse", WAREHOUSE_S3_PATH)
    # conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")

    # AWS credentials configuration
    # Try to get AWS credentials from default profile
    try:
        import boto3
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if credentials:
            print("🔑 Found AWS credentials, setting for Spark")
            # Set explicit credentials for Spark/Hadoop
            conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.s3.access-key-id", credentials.access_key)
            conf.set(f"spark.sql.catalog.{REMOTE_CATALOG_NAME}.s3.secret-access-key", credentials.secret_key)

            # Handle session token if present (for temporary credentials)
            if credentials.token:
                conf.set("spark.hadoop.fs.s3a.session.token", credentials.token)
                print("   - Using temporary credentials with session token")
            else:
                print("   - Using long-term credentials")
        else:
            print("⚠️  No AWS credentials found, falling back to default provider chain")
            conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")
    except ImportError:
        print("⚠️  boto3 not available, using default AWS credentials provider")
        conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")
    except Exception as e:
        print(f"⚠️  Error getting AWS credentials: {e}")
        print("   Falling back to default provider chain")
        conf.set("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain")

    # Get pod IP and set as driver host so executors can connect back
    pod_ip = os.environ.get('POD_IP')
    if not pod_ip:
        try:
            hostname = socket.gethostname()
            pod_ip = socket.gethostbyname(hostname)
        except:
            pod_ip = None
    
    if pod_ip:
        print(f"🔗 Setting driver host to pod IP: {pod_ip}")
        conf.set("spark.driver.host", pod_ip)
    else:
        print("⚠️  Could not determine pod IP - using default driver host")
    
    try:
        # Create Spark session
        spark = SparkSession.builder.config(conf=conf).getOrCreate()
        
        # Suppress common warnings by setting log levels
        sc = spark.sparkContext
        sc.setLogLevel("ERROR")  # Only show ERROR level messages
        
        # Suppress specific logger warnings
        log4j = sc._jvm.org.apache.log4j
        log4j.LogManager.getLogger("org.apache.hadoop").setLevel(log4j.Level.ERROR)
        log4j.LogManager.getLogger("org.apache.spark").setLevel(log4j.Level.ERROR)
        log4j.LogManager.getLogger("org.spark_project").setLevel(log4j.Level.ERROR)
        
        print("✅ Spark session created successfully!")
        print(f"   - Application ID: {spark.sparkContext.applicationId}")
        print(f"   - Executor instances: {executor_instances}")
        print(f"   - Executor memory: {executor_memory}")
        print(f"   - Executor cores: {executor_cores}")
        
        return spark
        
    except Exception as e:
        print(f"❌ Failed to create Spark session: {str(e)}")
        print(f"\n🔧 Debugging steps:")
        print(f"   1. Verify RBAC: kubectl auth can-i create pods --namespace {spark_namespace}")
        print(f"   2. Check namespace exists: kubectl get namespace {spark_namespace}")
        print(f"   3. Check service account files: ls -la /var/run/secrets/kubernetes.io/serviceaccount/")
        raise


def analyze_query_performance(spark, query):
    """
    Analyze query performance and provide optimization suggestions
    """
    print("🔍 Analyzing query performance...")
    
    # Get current configuration
    conf = spark.sparkContext.getConf()
    executors = int(conf.get("spark.executor.instances", "2"))
    executor_memory = conf.get("spark.executor.memory", "1g")
    executor_cores = int(conf.get("spark.executor.cores", "1"))
    
    print(f"📊 Current Spark Configuration:")
    print(f"   - Executors: {executors}")
    print(f"   - Executor Memory: {executor_memory}")
    print(f"   - Executor Cores: {executor_cores}")
    print(f"   - Total Cores: {executors * executor_cores}")
    
    # Run query with timing
    import time
    start_time = time.time()
    result = spark.sql(query)
    result.show()
    end_time = time.time()
    
    execution_time = end_time - start_time
    print(f"⏱️  Query execution time: {execution_time:.2f} seconds")
    
    # Get query plan
    print("\n📋 Query Execution Plan:")
    result.explain(True)
    
    return execution_time


def diagnose_table_performance(spark, table_name="iceberg.teehr.primary_timeseries"):
    """
    Diagnose table structure and performance characteristics
    """
    print(f"🔍 Diagnosing table: {table_name}")
    
    # Get table statistics
    try:
        stats_query = f"DESCRIBE EXTENDED {table_name}"
        stats_df = spark.sql(stats_query)
        print("\n📊 Table Statistics:")
        stats_df.show(100, truncate=False)
    except Exception as e:
        print(f"❌ Could not get table stats: {e}")
    
    # Check table partitioning
    try:
        partitions_query = f"SHOW PARTITIONS {table_name}"
        partitions_df = spark.sql(partitions_query)
        partition_count = partitions_df.count()
        print(f"\n📁 Table has {partition_count} partitions")
        if partition_count < 20:
            partitions_df.show()
    except Exception as e:
        print(f"⚠️  Could not get partition info: {e}")
    
    # Check data distribution by location_id
    try:
        print("\n🎯 Checking location_id distribution (sample):")
        sample_query = f"""
        SELECT location_id, count(*) as sample_count 
        FROM {table_name} TABLESAMPLE (1 PERCENT)
        GROUP BY location_id 
        ORDER BY sample_count DESC 
        LIMIT 20
        """
        spark.sql(sample_query).show()
    except Exception as e:
        print(f"❌ Could not sample data: {e}")
    
    # Check file count and sizes
    try:
        print("\n📁 File information:")
        files_query = f"SELECT COUNT(*) as file_count FROM {table_name}.files"
        spark.sql(files_query).show()
    except Exception as e:
        print(f"⚠️  Could not get file info: {e}")


def optimize_for_aggregation(spark):
    """
    Apply additional optimizations specifically for aggregation queries
    """
    print("🚀 Applying aggregation-specific optimizations...")
    
    # Increase executor memory fraction for aggregations
    spark.conf.set("spark.sql.adaptive.enabled", "true")
    spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
    spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "256MB")  # Larger partitions
    
    # Optimize for wide tables (many columns)
    spark.conf.set("spark.sql.codegen.wholeStage", "true")
    spark.conf.set("spark.sql.codegen.maxFields", "200")
    
    # Memory management for large aggregations
    spark.conf.set("spark.executor.memory", "3g")  # If possible
    spark.conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "20000")
    
    print("✅ Aggregation optimizations applied")


def optimize_for_pandas_udfs(spark):
    """
    Apply optimizations specifically for Pandas UDF aggregations
    Only sets configurations that can be modified at runtime
    """
    print("🐼 Applying Pandas UDF optimizations...")
    
    # Critical: Reduce shuffle partitions for UDF operations
    spark.conf.set("spark.sql.shuffle.partitions", "8")  # Much lower for UDFs
    
    # Arrow optimizations for Pandas UDFs
    spark.conf.set("spark.sql.execution.arrow.maxRecordsPerBatch", "5000")  # Smaller batches
    # Note: spark.sql.execution.arrow.pyspark.enabled is already set at session creation
    
    # Broadcast optimization for large IN clauses  
    spark.conf.set("spark.sql.adaptive.localShuffleReader.enabled", "true")
    spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")
    
    # Adaptive query execution settings
    spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
    spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", "64MB")  # Smaller for UDFs
    spark.conf.set("spark.sql.adaptive.coalescePartitions.minPartitionSize", "32MB")
    
    print("✅ Pandas UDF optimizations applied")
    print("⚠️  Note: Some optimizations (worker memory, reuse) must be set at session creation")
