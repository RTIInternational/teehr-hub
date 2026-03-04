"""Utility functions for working with datastream troute outputs."""
from typing import List
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import s3fs
from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE
import botocore
from botocore.exceptions import ClientError

from teehr.fetching.utils import write_timeseries_parquet_file
import teehr

S3_FS = s3fs.S3FileSystem(anon=True)


@task(cache_policy=NO_CACHE)
def load_to_warehouse(
    ev: teehr.Evaluation,
    in_path: Path,
    table_name: str,
):
    """Load cached parquet files into the warehouse."""
    logger = get_run_logger()
    logger.info(
        f"Loading troute output from cache to {table_name}"
    )
    ev.load.from_cache(
        in_path=in_path,
        table_name=table_name
    )
    logger.info("Successfully loaded data to warehouse")
    return


@task(cache_policy=NO_CACHE)
def coalesce_cache_files(
    ev: teehr.Evaluation,
    num_cache_files: int,
    output_cache_dir: Path,
    coalesced_cache_dir: Path,
):
    """Coalesce multiple parquet cache files into a single parquet file."""
    logger = get_run_logger()
    logger.info("Coalescing cache files for optimized loading")
    # Read the converted files to Spark DataFrame
    schema_func = ev.table(table_name="secondary_timeseries").schema_func
    sdf = ev.read.from_cache(
        path=output_cache_dir,
        table_schema_func=schema_func()
    ).to_sdf()
    sdf.coalesce(num_cache_files).write.mode("overwrite").parquet(str(coalesced_cache_dir))
    return


@task(cache_policy=NO_CACHE)
def generate_s3_filepaths(
    datastream_name: str,
    hydrofabric_version: str,
    yrmoday: str,
    forecast_configuration: str,
    members: List[str | None],
    ref_tz_hours: List[str],
    start_dt: datetime,
    s3: botocore.client.BaseClient,
    bucket_name: str,
) -> List[str]:
    """Generate a list of S3 filepaths for troute output files."""
    logger = get_run_logger()
    s3_filepaths = []
    for member in members:
        for ref_tz_hour in ref_tz_hours:
            if member is None:
                prefix = (
                    f"outputs/{datastream_name}/{hydrofabric_version}/ngen.{yrmoday}"
                    f"/{forecast_configuration}/{ref_tz_hour}/"
                )
            else:
                prefix = (
                    f"outputs/{datastream_name}/{hydrofabric_version}/ngen.{yrmoday}"
                    f"/{forecast_configuration}/{ref_tz_hour}/{member}/"
                )
            try:
                response = s3.list_objects_v2(
                    Bucket=bucket_name,
                    Prefix=prefix,
                    Delimiter='/',
                    MaxKeys=100
                )
            except ClientError as e:
                logger.error(f"Error listing objects in S3: {e}")
                continue

            # The troute filename currently uses the first valid time
            file_valid_time = f"{int(ref_tz_hour) + 1:02d}"
            # Construct reference time from s3 path
            ref_time = datetime.strptime(f"{yrmoday}{ref_tz_hour}", "%Y%m%d%H")

            # Get list of VPU prefixes
            vpu_prefixes = response.get('CommonPrefixes', [])
            for vpu_prefix in vpu_prefixes:
                # Medium range forecasts are broken into 10 daily files
                if forecast_configuration == "medium_range":
                    for i in range(0, 10):
                        yrmoday_i = (start_dt + timedelta(days=i)).strftime("%Y%m%d")
                        filepath = generate_single_filepath(
                                vpu_prefix=vpu_prefix,
                                yrmoday=yrmoday_i,
                                file_valid_time=file_valid_time,
                                bucket_name=bucket_name,
                            )
                        s3_filepaths.append(
                            {
                                "filepath": filepath,
                                "ref_time": ref_time,
                                "member": member
                            }
                        )
                else:
                    filepath = generate_single_filepath(
                        vpu_prefix=vpu_prefix,
                        yrmoday=yrmoday,
                        file_valid_time=file_valid_time,
                        bucket_name=bucket_name,
                    )
                    s3_filepaths.append(
                        {
                            "filepath": filepath,
                            "ref_time": ref_time,
                            "member": member
                        }
                    )
    return s3_filepaths


@task()
def generate_single_filepath(
    vpu_prefix: dict,
    yrmoday: str,
    file_valid_time: str,
    bucket_name: str,
) -> str:
    """Generate the S3 filepath for a given troute output file."""
    # Note. The vpu_prefix['Prefix'] includes the trailing slash
    filename = f"troute_output_{yrmoday}{file_valid_time}00.parquet"
    filepath = f"{vpu_prefix['Prefix']}ngen-run/outputs/troute/{filename}"
    s3_filepath = f"s3://{bucket_name}/{filepath}"
    return s3_filepath


@task()
def fetch_troute_output_to_cache(
    filepath_info: dict,
    warehouse_ngen_ids: List[int],
    unit_name: str,
    variable_name: str,
    configuration_name: str,
    location_id_prefix: str,
    output_cache_dir: Path,
    bucket_name: str,
):
    """Fetch troute output from S3 and return as a pandas DataFrame."""
    logger = get_run_logger()
    s3_filepath = filepath_info["filepath"]
    reference_time = filepath_info["ref_time"]
    member = filepath_info["member"]
    logger.info(f"Processing file: {s3_filepath}")
    try:
        # Load as a pyarrow table.
        filters = [("feature_id", "in", warehouse_ngen_ids)]
        table = pq.read_table(
            s3_filepath,
            filesystem=S3_FS,
            filters=filters
        )
        logger.info("Successfully opened file")
    except Exception as e:
        logger.warning(f"Error reading file {e}")
        return None

    n_rows = table.num_rows
    logger.info(f"Number of rows in file: {n_rows}")

    units_name = [unit_name] * n_rows
    variable_name = [variable_name] * n_rows
    configuration_name = [configuration_name] * n_rows
    reference_time = [reference_time] * n_rows
    member = [None] * n_rows

    teehr_table = pa.table(
        data={
            "location_id": table["feature_id"],
            "value_time": table["time"],
            "value": table["flow"],
            "unit_name": units_name,
            "variable_name": variable_name,
            "configuration_name": configuration_name,
            "reference_time": reference_time,
            "member": member
        }
    )

    # Add prefix to location ID.
    new_col = pc.binary_join_element_wise(
        location_id_prefix + "-",
        pc.cast(teehr_table.column("location_id"), pa.string()),
        ""
    )
    teehr_table = teehr_table.set_column(
        teehr_table.schema.get_field_index("location_id"),
        "location_id",
        new_col
    )

    if teehr_table.num_rows == 0:
        logger.warning(
            f"No data found in file: {s3_filepath}"
        )
        return None

    # Write to the cache with a unique filename
    parquet_filename = Path(s3_filepath).name
    filepath_prefix = Path(s3_filepath).relative_to(f"s3:/{bucket_name}/outputs/").parents[1].as_posix()
    unique_filename = f"{
        filepath_prefix
        .replace('/', '_')
        .replace('.', '_')
        .replace('-', '_')
    }_{parquet_filename}"
    cache_filepath = output_cache_dir / unique_filename
    logger.info(
        f"Caching fetched data to: {cache_filepath}"
    )
    write_timeseries_parquet_file(
        filepath=cache_filepath,
        data=teehr_table,
        timeseries_type="secondary",
        overwrite_output=False
    )

    return
