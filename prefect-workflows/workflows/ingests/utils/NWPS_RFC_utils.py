from typing import List
from datetime import datetime, timedelta
from pathlib import Path

import xarray as xr
from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE

from teehr.fetching.utils import write_timeseries_parquet_file
import teehr

import requests
import pandas as pd


@task(cache_policy=NO_CACHE)
def generate_NWPS_endpoints(
    gage_ids: List[str],
    root_url: str,
) -> List[dict]:
    """Generate API endpoints for NWPS RFC forecasts."""
    logger = get_run_logger()
    logger.info("Generating NWPS RFC API endpoints...")

    endpoints = []
    for id in gage_ids:
        metadata_endpoint = f"{root_url}/nwps/v1/gauges/{id}"
        fcst_endpoint = f"{root_url}/nwps/v1/gauges/{id}/stageflow/forecast"
        endpoint = {
            "usgs_id": id,
            "metadata": metadata_endpoint,
            "forecast": fcst_endpoint
        }
        endpoints.append(endpoint)

    logger.info(f"Generated {len(endpoints)} NWPS RFC API endpoints.")
    return endpoints


@task()
def fetch_NWPS_RFC_fcst_to_cache(
    endpoint: dict,
    output_cache_dirs: dict,
    field_mapping: dict,
    units_mapping: dict,
    variable_name: list,
    configuration_name: str,
    location_id_prefix: str,
):
    """Fetch NWPS RFC forecast data and write to parquet cache."""
    logger = get_run_logger()
    usgs_id = endpoint["usgs_id"]

    # Fetch forecast data
    fcst_url = endpoint["forecast"]
    response = requests.get(fcst_url)
    if response.status_code != 200:
        logger.warning(f"Failed to fetch NWPS RFC forecast data for USGS ID: {usgs_id}")
        return
    fcst_data = response.json()

    # extract data to dataframe
    df = pd.DataFrame(fcst_data['data'])
    if df.empty:
        logger.warning(f"No forecast data available for USGS ID: {usgs_id}")
        return

    # trim to required fields
    field_list = [field for field in field_mapping if field in df.columns]
    df = df[field_list]
    df.rename(columns=field_mapping, inplace=True)

    # convert flow units (kcfs to cms)
    df["value"] = df["value"] * 28.3168

    # Add prefix to location ID (nwpsrfc)
    df["location_id"] = location_id_prefix + "-" + usgs_id

    # determine timestep to inform variable_name
    df['value_time'] = pd.to_datetime(df['value_time'])
    df = df.sort_values(by="value_time")
    time_diffs = df["value_time"].diff().dropna().unique()
    time_diffs_hours = time_diffs / pd.Timedelta(hours=1)
    if len(time_diffs_hours) == 1:
        timestep_hours = int(time_diffs_hours[0])
        if timestep_hours == 1:
            variable_name = variable_name[0]
        elif timestep_hours == 6:
            variable_name = variable_name[1]
        else:
            logger.warning(
                f"Unexpected timestep of {timestep_hours} hours for USGS ID: {usgs_id}."
            )
            return
    else:
        logger.warning(
            f"Multiple timesteps detected for USGS ID: {usgs_id}. Cannot determine variable name."
            f"Timesteps detected: {time_diffs}"
        )
        return

    # assume reference_time is one timestep before first forecast value time
    reference_time = df["value_time"].min()
    if variable_name == "streamflow_hourly_inst":
        reference_time = reference_time - pd.Timedelta(hours=1)
    else:
        reference_time = reference_time - pd.Timedelta(hours=6)

    # Assemble dataframe
    unit_name = units_mapping[variable_name]
    df["reference_time"] = reference_time
    df["variable_name"] = variable_name
    df["configuration_name"] = configuration_name
    df["unit_name"] = unit_name
    df["member"] = None
    df = df[[
        "reference_time",
        "value_time",
        "value",
        "variable_name",
        "configuration_name",
        "unit_name",
        "location_id",
        "member"
    ]]

    # write to the cache as parquet with unique filename
    parquet_filename = f"nwpsrfc_forecast_{usgs_id}.parquet"
    cache_filepath = output_cache_dirs[variable_name] / parquet_filename
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
