"""Utility functions for working with nwm31se troute outputs."""
from typing import List
from datetime import datetime, timedelta
from pathlib import Path

import xarray as xr
from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE

from teehr.fetching.utils import write_timeseries_parquet_file
import teehr

import requests
from urllib.error import URLError
from bs4 import BeautifulSoup

# sample endpoint for forecast_configuration = "short_range":
# https://hydrology.nws.noaa.gov/pub/nwm/v3.1/wcoss-data/nwm.20260121/short_range/nwm.t00z.short_range.channel_rt.f001.conus.nc
# f'{root_url}/nwm.{yrmoday}/{forecast_configuration}/nwm.t{ref_tz_hour}z.{forecast_configuration}.channel_rt.f{forecast_hour:03d}.conus.nc'

# sample endpoint for forecast_configuration = "medium_range" and member = 1:
# https://hydrology.nws.noaa.gov/pub/nwm/v3.1/wcoss-data/nwm.20260121/medium_range_mem1/nwm.t00z.medium_range.channel_rt_1.f001.conus.nc
# f'{root_url}/nwm.{yrmoday}/{forecast_configuration}_mem{member}/nwm.t{ref_tz_hour}z.{forecast_configuration}.channel_rt_{member}.f{forecast_hour:03d}.conus.nc'

# sample endpoint for forecast_configuration = "medium_range_blend" and member = 1 (not considered):
# https://hydrology.nws.noaa.gov/pub/nwm/v3.1/wcoss-data/nwm.20260121/medium_range_blend_mem1/nwm.t00z.medium_range_blend.channel_rt_1.f001.conus.nc
# f'{root_url}/nwm.{yrmoday}/{forecast_configuration}_blend_mem{member}/nwm.t{ref_tz_hour}z.{forecast_configuration}_blend.channel_rt_{member}.f{forecast_hour:03d}.conus.nc'


@task(cache_policy=NO_CACHE)
def generate_nwm31se_endpoints(
    root_url: str,
    yrmoday: str,
    forecast_configuration: str,
    members: List[str | None],
    ref_tz_hours: List[str],
    start_dt: datetime,
) -> List[str]:
    """Generate NWM31SE endpoints list."""
    logger = get_run_logger()
    logger.info("Generating NWM31SE endpoints list")

    endpoints = []
    for member in members:
        for ref_tz_hour in ref_tz_hours:
            if member is None: # short_range has no members
                prefix = (
                    f"{root_url}/nwm.{yrmoday}/{forecast_configuration}/"
                    )
            else:
                prefix = (
                    f"{root_url}/nwm.{yrmoday}/{forecast_configuration}_mem{member}/"
                    )
                # FUTURE: would add blended here if considered
            try:
                # validate that the prefix URL is accessible
                response = requests.head(prefix, timeout=5)
                response.raise_for_status()

                # get list of files containing 'channel_rt' in name
                soup = BeautifulSoup(response.content, 'html.parser')
                files = []
                for link in soup.find_all('a'):
                    href = link.get('href')
                    if 'channel_rt' in href:
                        files.append(href)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error accessing URL {prefix}: {e}")
                continue

            # construct full endpoints
            for file in files:

                endpoint = {
                    "endpoint": file,
                    "ref_time": datetime.strptime(
                        f"{yrmoday}{ref_tz_hour}",
                        "%Y%m%d%H"
                        ),
                    "member": member
                }

                endpoints.append(endpoint)

    return endpoints


@task()
def fetch_channelrt_output_to_cache(
    filepath_info: dict,
    warehouse_ngen_ids: List[str],
    field_mapping: dict,
    units_mapping: dict,
    variable_name: str,
    configuration_name: str,
    location_id_prefix: str,
    output_cache_dir: Path,
) -> None:
    """Fetch channel_rt output from NWM31SE endpoint to cache."""
    logger = get_run_logger()
    endpoint = filepath_info['endpoint']
    ref_time = filepath_info['ref_time']
    member = filepath_info['member']

    try:
        ds = xr.open_dataset(endpoint)
        logger.info("Successfully opened file")
    except URLError as e:
        logger.error(f"Error accessing endpoint {endpoint}: {e}")
        return None

    # Filter dataset
    mask = ds['feature_id'].isin(warehouse_ngen_ids)
    ds = ds.where(mask, drop=True)
    field_list = [field for field in field_mapping if field in ds]
    ds = ds[field_list]

    # convert to pandas, rename columns
    df = ds.to_dataframe().reset_index()
    df.rename(columns=field_mapping, inplace=True)

    # add prefix to location ID (nwm31se)
    df["location_id"] = location_id_prefix + "-" + df.location_id.astype(str)

    # ensure data is present
    if df.empty:
        logger.warning(
            f"No data found in endpoint: {endpoint}"
        )
        return None

    # map constant field values
    unit_name = units_mapping[ds.flow.units]
    constant_field_values = {
        "unit_name": unit_name,
        "variable_name": variable_name,
        "configuration_name": configuration_name,
        "reference_time": ref_time,
        "member": member
    }
    for key in constant_field_values.keys():
        df[key] = constant_field_values[key]

    # write to cache with unique filename
    parquet_filename = endpoint.split("/")[-1].replace(".nc", ".parquet")
    parent_prefix = endpoint.split("/")[-3]  # e.g., nwm.YYYYMMDD
    unique_filename = f"{parent_prefix}-{parquet_filename}"
    cache_filepath = Path(output_cache_dir, unique_filename)
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
