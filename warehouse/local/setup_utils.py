from teehr.evaluation.spark_session_utils import create_spark_session


# Handpicked sites that seemed interesting
DEV_LOCATION_ID_LIST = [
    # CONUS
    "usgs-02424000",
    "usgs-03068800",
    "usgs-01570500",
    "usgs-01347000",
    "usgs-05443500",
    "usgs-06770500",
    "usgs-08313000",
    "usgs-11421000",
    "usgs-14319500",
    # Alaska
    "usgs-15200280",
    "usgs-15209700",
    "usgs-15209750",
    "usgs-15214000",
    # Hawaii
    "usgs-16010000",
    "usgs-16019000",
    "usgs-16031000",
    "usgs-16060000",
    # Puerto Rico
    "usgs-50010500",
    "usgs-50011000",
    "usgs-50011085",
    "usgs-50011128"
]

def create_minio_spark_session():
    """Start a Spark session with MinIO credentials and custom configuration."""
    return create_spark_session(
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin123",
    update_configs={
        "spark.hadoop.fs.s3a.aws.credentials.provider":
        "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider"
    }
)