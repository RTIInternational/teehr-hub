"""Utility functions for working with datastream troute outputs."""
from typing import List
from datetime import datetime, timedelta
from pathlib import Path

import xarray as xr
from prefect import task, get_run_logger
import botocore
from botocore.exceptions import ClientError

from teehr.fetching.utils import write_timeseries_parquet_file


@task()
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
    filename = f"troute_output_{yrmoday}{file_valid_time}00.nc"
    filepath = f"{vpu_prefix['Prefix']}ngen-run/outputs/troute/{filename}"
    s3_filepath = f"s3://{bucket_name}/{filepath}"
    return s3_filepath


@task()
def fetch_troute_output_to_cache(
    filepath_info: dict,
    warehouse_ngen_ids: List[str],
    field_mapping: dict,
    units_mapping: dict,
    variable_name: str,
    configuration_name: str,
    location_id_prefix: str,
    output_cache_dir: Path,
    bucket_name: str,
):
    """Fetch troute output from S3 and return as a pandas DataFrame."""
    logger = get_run_logger()
    s3_filepath = filepath_info["filepath"]
    ref_time = filepath_info["ref_time"]
    member = filepath_info["member"]
    logger.info(f"Processing file: {s3_filepath}")
    try:
        # Open the dataset with xarray, specifying the engine
        ds = xr.open_dataset(
            s3_filepath,
            engine="h5netcdf",
            backend_kwargs={"storage_options": {'anon': True}}
        )
        logger.info("Successfully opened file")
    except Exception as e:
        logger.warning(f"Error reading file {e}")
        return None

    # Subset the xarray dataset to only include locations in the warehouse
    mask = ds['feature_id'].isin(warehouse_ngen_ids)
    ds = ds.where(mask, drop=True)
    # Subset the xarray dataset to only include fields that we need
    field_list = [field for field in field_mapping if field in ds]
    # Convert to pandas DataFrame and rename columns
    df = ds[field_list].to_dataframe()
    df.reset_index(inplace=True)
    df.rename(columns=field_mapping, inplace=True)
    unit_name = units_mapping[ds.flow.units]
    # Add prefix to location ID (nrds22)
    df["location_id"] = location_id_prefix + "-" + df.location_id.astype(str)

    if df.empty:
        logger.warning(
            f"No data found in file: {s3_filepath}"
        )
        return None

    constant_field_values = {
        "unit_name": unit_name,
        "variable_name": variable_name,
        "configuration_name": configuration_name,
        "reference_time": ref_time,
        "member": member
    }
    for key in constant_field_values.keys():
        df[key] = constant_field_values[key]

    # Write to the cache with a unique filename
    parquet_filename = Path(s3_filepath).name.replace(".nc", ".parquet")
    filepath_prefix = Path(s3_filepath).relative_to(f"s3:/{bucket_name}/outputs/").parent.as_posix()
    unique_filename = f"{filepath_prefix.replace('/', '_')}_{parquet_filename}"
    cache_filepath = output_cache_dir / unique_filename
    logger.info(
        f"Caching fetched data to: {cache_filepath}"
    )
    write_timeseries_parquet_file(
        filepath=cache_filepath,
        data=df,
        timeseries_type="secondary",
        overwrite_output=False
    )

    return
