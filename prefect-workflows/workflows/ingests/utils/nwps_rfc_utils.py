from typing import List

from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE

from teehr.fetching.utils import write_timeseries_parquet_file

import requests
import pandas as pd


@task(cache_policy=NO_CACHE)
def generate_nwps_endpoints(
    gage_ids: List[str],
    root_url: str,
    ev: object,
) -> List[dict]:
    """Generate API endpoints for NWPS RFC forecasts."""
    logger = get_run_logger()
    logger.info("Generating NWPS RFC API endpoints...")

    endpoints = []
    for id in gage_ids:
        max_ref_time = query_last_reference_time(gage_id=id, ev=ev)
        metadata_endpoint = f"{root_url}/nwps/v1/gauges/{id}"
        fcst_endpoint = f"{root_url}/nwps/v1/gauges/{id}/stageflow/forecast"
        endpoint = {
            "RFC_lid": id,
            "metadata": metadata_endpoint,
            "forecast": fcst_endpoint,
            "last_reference_time": max_ref_time
        }
        endpoints.append(endpoint)

    logger.info(f"Generated {len(endpoints)} NWPS RFC API endpoints.")
    return endpoints


@task(cache_policy=NO_CACHE)
def query_last_reference_time(
    gage_id: str,
    ev: object,
) -> pd.Timestamp:
    """Query the most recent reference time for a given gage."""
    formatted_id = 'nwpsrfc-' + gage_id
    max_reference_time = ev.secondary_timeseries.to_sdf().filter(
        f"location_id == '{formatted_id}'"
    ).groupby().agg(
        {"reference_time": "max"}
    ).collect()[0][0]

    max_reference_time = pd.to_datetime(max_reference_time, utc=True)

    return max_reference_time


@task()
def fetch_nwps_rfc_fcst_to_cache(
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
    RFC_lid = endpoint["RFC_lid"]

    # Fetch forecast data
    fcst_url = endpoint["forecast"]
    try:
        response = requests.get(fcst_url)
        response.raise_for_status()
        fcst_data = response.json()
    except requests.exceptions.RequestException as e:
        logger.warning(
            f"Failed to fetch NWPS RFC forecast data for RFC LID: {RFC_lid} "
            f"- Error: {str(e)}")
        return

    # extract data to dataframe
    df = pd.DataFrame(fcst_data['data'])
    if df.empty:
        logger.warning(f"No forecast data available for RFC LID: {RFC_lid}")
        return

    # trim to required fields
    field_list = [field for field in field_mapping if field in df.columns]
    df = df[field_list]
    df.rename(columns=field_mapping, inplace=True)

    # convert flow units (kcfs to cms)
    df["value"] = df["value"] * 28.3168

    # Add prefix to location ID (nwpsrfc)
    df["location_id"] = location_id_prefix + "-" + RFC_lid

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
                f"Unexpected timestep of {timestep_hours} hours "
                f"for RFC LID: {RFC_lid}."
            )
            return
    else:
        logger.warning(
            f"Multiple timesteps detected for RFC LID: {RFC_lid}."
            "Cannot determine variable name."
            f"Timesteps detected: {time_diffs}"
        )
        return

    # assume reference_time is one timestep before first forecast value time
    reference_time = df["value_time"].min()
    reference_time = pd.Timestamp(reference_time)
    if variable_name == "streamflow_hourly_inst":
        reference_time = reference_time - pd.Timedelta(hours=1)
    else:
        reference_time = reference_time - pd.Timedelta(hours=6)

    # Add check to skip if reference_time is not newer than last cached 
    # reference_time
    last_reference_time = endpoint["last_reference_time"]
    if (last_reference_time is not None and
       reference_time <= last_reference_time):
        logger.info(
            f"Skipping fetch for RFC LID: {RFC_lid} - "
            f"Reference time {reference_time} is not newer than last cached "
            f"reference time {last_reference_time}."
        )
        return

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

    # create cache directory if it doesn't exist
    output_cache_dir = output_cache_dirs[variable_name]
    if not output_cache_dir.exists():
        output_cache_dir.mkdir(parents=True, exist_ok=True)

    # write to the cache as parquet with unique filename
    parquet_filename = f"nwpsrfc_forecast_{RFC_lid}.parquet"
    cache_filepath = output_cache_dir / parquet_filename
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
