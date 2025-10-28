from typing import Union
from pathlib import Path
import shutil
import logging

from prefect import flow, get_run_logger

import teehr
from teehr.evaluation.spark_session_utils import create_spark_session

DEFAULT_DEV_WAREHOUSE_DIR = "/data/temp_warehouse"

# Handpicked sites that seemed interesting
USGS_GAGES = [
    "usgs-02424000",
    "usgs-03068800",
    "usgs-01570500",
    "usgs-01347000",
    "usgs-05443500",
    "usgs-06770500",
    "usgs-08313000",
    "usgs-11421000",
    "usgs-14319500"
]

logging.getLogger("teehr").setLevel(logging.INFO)


@flow(flow_run_name="initialize-dev-warehouse")
def initialize_dev_warehouse(
    dir_path: Union[Path, str] = DEFAULT_DEV_WAREHOUSE_DIR
):
    """Initialize Development Data Warehouse."""    
    logger = get_run_logger()
    
    logger.info("Creating spark session")
    spark = create_spark_session(
        aws_access_key_id="minioadmin",
        aws_secret_access_key="minioadmin123"
    )
    
    logger.info(f"Initializing dev warehouse at: {dir_path}")
    shutil.rmtree(dir_path, ignore_errors=True)
    ev = teehr.Evaluation(
        spark=spark,
        dir_path=dir_path,
        create_dir=True
    )   
    
    # Copy local template
    ev.clone_template()
    ev.enable_logging()
    
    # By default local catalog is source, and remote catalog is target.
    ev.apply_schema_migration()
    
    ev.set_active_catalog("remote")
    
    # Start loading data.
    options = {
        "header": "true",
        "ignoreMissingFiles": "true"
    }

    # Locations.
    tbl = ev.locations()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/locations/"
    sdf = spark.read.format("parquet").options(**options).load(s3_dirpath, schema=schema) 
    df = sdf.toPandas()
    locs_df = df[df["id"].isin(USGS_GAGES)]
    ev.write.to_warehouse(table_name="locations", source_data=locs_df)

    # Attributes.
    tbl = ev.attributes()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/attributes/"
    sdf = spark.read.format("csv").options(**options).load(s3_dirpath, schema=schema) 
    ev.write.to_warehouse(table_name="attributes", source_data=sdf)
    
    # Location Attributes.
    tbl = ev.location_attributes()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/location_attributes/"
    sdf = spark.read.format("parquet").options(**options).load(s3_dirpath, schema=schema) 
    sdf = sdf.filter(sdf.location_id.isin(USGS_GAGES))
    ev.write.to_warehouse(table_name="location_attributes", source_data=sdf)
    
    # Location Crosswalks.
    tbl = ev.location_crosswalks()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/location_crosswalks/"
    sdf = spark.read.format("parquet").options(**options).load(s3_dirpath, schema=schema) 
    sdf = sdf.filter(sdf.primary_location_id.isin(USGS_GAGES))
    ev.write.to_warehouse(table_name="location_crosswalks", source_data=sdf)
    
    # Units.
    tbl = ev.units()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/units/"
    sdf = spark.read.format("csv").options(**options).load(s3_dirpath, schema=schema) 
    ev.write.to_warehouse(table_name="units", source_data=sdf)
    
    # Variables.
    tbl = ev.variables()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/variables/"
    sdf = spark.read.format("csv").options(**options).load(s3_dirpath, schema=schema) 
    ev.write.to_warehouse(table_name="variables", source_data=sdf)
    
    # Configurations.
    tbl = ev.configurations()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/configurations/"
    sdf = spark.read.format("csv").options(**options).load(s3_dirpath, schema=schema) 
    ev.write.to_warehouse(table_name="configurations", source_data=sdf)
    
    # Primary Timeseries.
    tbl = ev.primary_timeseries()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/primary_timeseries/"
    sdf = spark.read.format("parquet").options(**options).load(s3_dirpath, schema=schema) 
    sdf = sdf.filter(sdf.location_id.isin(USGS_GAGES))
    ev.write.to_warehouse(table_name="primary_timeseries", source_data=sdf)
    
    # Secondary Timeseries.
    tbl = ev.secondary_timeseries()
    schema = tbl.schema_func().to_structtype()
    s3_dirpath = "s3a://ciroh-rti-public-data/teehr-data-warehouse/v0_4_evaluations/e3_usgs_hourly_streamflow/dataset/secondary_timeseries/"
    sdf = spark.read.format("parquet").options(**options).load(s3_dirpath, schema=schema) 
    xwalk_df = ev.location_crosswalks.to_pandas()
    sdf = sdf.filter(sdf.location_id.isin(xwalk_df.secondary_location_id.tolist()))
    ev.write.to_warehouse(table_name="secondary_timeseries", source_data=sdf)
    
    logger.info(f"Development data warehouse initialized at: {dir_path}")