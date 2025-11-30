"""Utility functions for working with datastream troute outputs."""
from typing import List
from datetime import datetime

import xarray as xr
from prefect import task, get_run_logger


@task()
def fetch_troute_output_as_dataframe(
    s3_filepath: str,
    storage_options: dict,
    warehouse_ngen_ids: List[str],
    field_mapping: dict,
    units_mapping: dict,
    variable_name: str,
    configuration_name: str,
    ref_time: datetime,
    location_id_prefix: str
):
    """Fetch troute output from S3 and return as a pandas DataFrame."""
    try:
        logger = get_run_logger()
        # Open the dataset with xarray, specifying the engine
        ds = xr.open_dataset(
            s3_filepath,
            engine="h5netcdf",
            backend_kwargs={"storage_options": storage_options}
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
        "member": None
    }
    for key in constant_field_values.keys():
        df[key] = constant_field_values[key]

    return df
