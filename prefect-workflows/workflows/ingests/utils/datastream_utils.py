"""Utility functions for working with datastream troute outputs."""
from typing import List
from datetime import datetime
from pathlib import Path

import xarray as xr
from prefect import task, get_run_logger

from teehr.fetching.utils import write_timeseries_parquet_file


@task()
def fetch_troute_output_to_cache(
    vpu_prefix: dict,
    bucket_name: str,
    yrmoday: str,
    file_valid_time: str,
    warehouse_ngen_ids: List[str],
    field_mapping: dict,
    units_mapping: dict,
    variable_name: str,
    configuration_name: str,
    ref_time: datetime,
    location_id_prefix: str,
    output_cache_dir: Path,
    member: str | None
):
    """Fetch troute output from S3 and return as a pandas DataFrame."""
    logger = get_run_logger()

    # Note. The vpu_prefix['Prefix'] includes the trailing slash
    filename = f"troute_output_{yrmoday}{file_valid_time}00.nc"
    filepath = f"{vpu_prefix['Prefix']}ngen-run/outputs/troute/{filename}"
    s3_filepath = f"s3://{bucket_name}/{filepath}"
    logger.info(f"Processing file: {s3_filepath}")
    try:
        # Open the dataset with xarray, specifying the engine
        ds = xr.open_dataset(
            s3_filepath,
            engine="h5netcdf",
            backend_kwargs={"storage_options": {'anon': True}}
        )
        logger.info(f"Successfully opened file: {s3_filepath}")
    except Exception as e:
        logger.error(f"Error reading file {s3_filepath}: {e}")
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
    unique_filename = f"{vpu_prefix['Prefix'].replace('/', '_')}{parquet_filename}"
    cache_filepath = output_cache_dir / unique_filename
    logger.info(
        f"Caching fetched data to: {cache_filepath}"
    )
    write_timeseries_parquet_file(
        filepath=cache_filepath,
        data=df,
        timeseries_type="secondary",
        overwrite_output=True
    )

    return
