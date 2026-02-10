from typing import List
from pathlib import Path

from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE

from teehr.fetching.utils import write_timeseries_parquet_file
import teehr

import requests
import pandas as pd


@task(cache_policy=NO_CACHE)
def query_last_reference_times(
    stripped_ids: List[str],
    ev: object,
) -> dict:
    """Query the most recent reference time for all gages at once."""
    logger = get_run_logger()

    # reformat stripped_ids for query
    formatted_ids = [f'nwpsrfc-{id}' for id in stripped_ids]

    # build filter condition
    id_list = ','.join([f"'{id}'" for id in formatted_ids])
    filter_condition = f"location_id IN ({id_list})"

    # Query once for all locations
    result_df = ev.secondary_timeseries.to_sdf().filter(
        filter_condition
    ).groupby("location_id").agg(
        {"reference_time": "max"}
    ).withColumnRenamed(
        "max(reference_time)",
        "reference_time"
    ).toPandas()

    # Build dict mapping stripped_id -> last_reference_time
    ref_times_dict = {}
    for idx, row in result_df.iterrows():
        # Strip the 'nwpsrfc-' prefix to get back to stripped_id
        stripped_id = row['location_id'].replace('nwpsrfc-', '')
        ref_times_dict[stripped_id] = pd.to_datetime(
            row['reference_time'],
            utc=True
            )

    logger.info(f"Queried reference times for {len(ref_times_dict)} gages.")
    return ref_times_dict


@task(cache_policy=NO_CACHE)
def generate_nwps_endpoints(
    gage_ids: List[str],
    root_url: str,
    last_reference_times: dict,
) -> List[dict]:
    """Generate API endpoints for NWPS RFC forecasts."""
    logger = get_run_logger()
    logger.info("Generating NWPS RFC API endpoints...")

    endpoints = []
    for id in gage_ids:
        metadata_endpoint = f"{root_url}/nwps/v1/gauges/{id}"
        fcst_endpoint = f"{root_url}/nwps/v1/gauges/{id}/stageflow/forecast"
        endpoint = {
            "RFC_lid": id,
            "metadata": metadata_endpoint,
            "forecast": fcst_endpoint,
            "last_reference_time": last_reference_times.get(id)
        }
        endpoints.append(endpoint)

    logger.info(f"Generated {len(endpoints)} NWPS RFC API endpoints.")
    return endpoints


@task()
def fetch_nwps_rfc_fcst_to_cache(
    nwps_endpoints: List[dict],
    output_cache_dir: str,
    field_mapping: dict,
    units_mapping: dict,
    variable_names: list,
    configuration_name: str,
    location_id_prefix: str,
):
    """Fetch NWPS RFC forecast data for chunk of endpoints, write to cache."""
    logger = get_run_logger()

    # create cache directory if it doesn't exist
    cache_dir_path = Path(output_cache_dir)
    if not cache_dir_path.exists():
        cache_dir_path.mkdir(parents=True, exist_ok=True)

    for endpoint in nwps_endpoints:
        RFC_lid = endpoint["RFC_lid"]

        # Fetch forecast data
        fcst_url = endpoint["forecast"]
        try:
            response = requests.get(fcst_url)
            response.raise_for_status()
            fcst_data = response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Failed to fetch RFC forecast data for RFC LID: {RFC_lid}"
                f"- Error: {str(e)}")
            continue

        # extract data to dataframe
        df = pd.DataFrame(fcst_data['data'])
        if df.empty:
            logger.warning(
                f"No forecast data available for RFC LID: {RFC_lid}"
                )
            continue

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
                variable_name = variable_names[0]
            elif timestep_hours == 6:
                variable_name = variable_names[1]
            else:
                logger.warning(
                    f"Unexpected timestep of {timestep_hours} hours "
                    f"for RFC LID: {RFC_lid}."
                )
                continue
        else:
            logger.warning(
                f"Multiple timesteps detected for RFC LID: {RFC_lid}."
                "Cannot determine variable name."
                f"Timesteps detected: {time_diffs}"
            )
            continue

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
            continue

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
        parquet_filename = f"nwpsrfc_forecast_{RFC_lid}.parquet"
        cache_filepath = cache_dir_path / parquet_filename
        logger.info(
            f"Caching fetched data to: {cache_filepath}"
        )
        write_timeseries_parquet_file(
            filepath=cache_filepath,
            data=df,
            timeseries_type="secondary",
            overwrite_output=False
        )


@task()
def has_cache_data(cache_dir: Path) -> bool:
    """Check if cache directory contains any parquet files."""
    if not cache_dir.exists():
        return False
    parquet_files = list(cache_dir.rglob("*.parquet"))
    return len(parquet_files) > 0


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
    sdf = ev.spark.read.parquet(str(output_cache_dir / "**/*.parquet"))
    sdf.coalesce(num_cache_files).write.mode("overwrite").parquet(
        str(coalesced_cache_dir)
        )
    return
