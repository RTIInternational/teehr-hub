"""Download teehr's Spark packages into the Ivy cache at SPARK_JARS_IVY.

Run at image build time so Spark sessions start from the cache instead of
downloading ~1 GB from Maven Central, which rate-limits per IP. The package
list comes from the installed teehr, so the cache matches its version.

Copy of teehr-cloud-core/jupyterhub-docker/warm-spark-ivy-cache.py. Keep the
two in sync.

Usage: python warm-spark-ivy-cache.py [--authmanager]
"""
import sys

from pyspark import SparkConf
from pyspark.sql import SparkSession
from teehr.evaluation import spark_session_utils as ssu

conf = ssu._create_spark_base_session(
    SparkConf(), "us-east-1", driver_memory="1g", driver_maxresultsize="1g"
)
if "--authmanager" in sys.argv:
    packages = ssu._build_polaris_auth_packages(True)
    repositories = ssu._build_polaris_auth_repositories(True)
    ssu._append_csv_conf(conf, "spark.jars.packages", packages)
    ssu._append_csv_conf(conf, "spark.jars.repositories", repositories)

SparkSession.builder.config(conf=conf).getOrCreate().stop()
