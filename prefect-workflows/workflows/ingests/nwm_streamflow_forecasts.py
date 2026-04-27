from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger, task
from prefect.cache_policies import NO_CACHE
import pandas as pd
import pyspark.sql as ps

from teehr import Configuration, Evaluation, Variable
from teehr.fetching.nwm.nwm_points import nwm_to_parquet
from teehr.utils.utils import remove_dir_if_exists
from teehr.fetching.utils import (
    format_nwm_configuration_metadata
)
from teehr.fetching.const import (
    NWM_VARIABLE_MAPPER,
    NWM_HAWAII_VARIABLE_MAPPER,
    VARIABLE_NAME
)
from teehr.models.fetching.utils import TimeseriesTypeEnum
from workflows.utils.common_utils import initialize_evaluation

# Start up a local Dask cluster
from dask.distributed import Client

logging.getLogger("teehr").setLevel(logging.INFO)


LOOKBACK_DAYS = 1
LOCATION_ID_PREFIX = "nwm30"
OCONUS_STATE_NAMES = [
    'Northern Mariana Islands', 'Alaska', 'Hawaii', 'Guam',
    'American Samoa', 'Puerto Rico', 'Virgin Islands'
]


@task(cache_policy=NO_CACHE)
def _filter_crosswalk_table(
    ev: Evaluation,
    configuration_name: str,
    location_id_prefix: str,
) -> ps.DataFrame:
    """Filter the location crosswalk table for the given configuration domain."""
    logger = get_run_logger()
    # Create the state_name filter based on configuration name
    if "hawaii" in configuration_name.lower():
        state_filter = f"state_name = 'Hawaii'"
    elif "alaska" in configuration_name.lower():
        state_filter = f"state_name = 'Alaska'"
    elif "puertorico" in configuration_name.lower():
        state_filter = f"state_name = 'Puerto Rico'"
    else:
        oconus_states = ", ".join(f"'{s}'" for s in OCONUS_STATE_NAMES)
        state_filter = f"state_name NOT IN ({oconus_states})"
    logger.info(f"Location crosswalk domain filter: {state_filter}")
    # Filter by state and location ID prefix
    filtered_crosswalks_sdf = ev.location_crosswalks.add_attributes(
        attr_list=["state_name"]
    ).filter(
        filters=[
            {
                "column": "secondary_location_id",
                "operator": "like",
                "value": f"{location_id_prefix}-%"
            },
            state_filter
        ]
    ).to_sdf()
    return filtered_crosswalks_sdf


@flow(
    flow_run_name="ingest-nwm-streamflow-forecasts",
    timeout_seconds=60 * 60
)
def ingest_nwm_streamflow_forecasts(
    temp_dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp, None] = None,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    nwm_configuration: str = "short_range",
    nwm_version: str = "nwm30",
    output_type: str = "channel_rt",
    variable_name: str = "streamflow",
    start_spark_cluster: bool = False,
    timeseries_type: Union[TimeseriesTypeEnum, str] = "secondary"
) -> None:
    """NWM Streamflow Forecasts Ingestion.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing NWM forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    """
    logger = get_run_logger()
    client = Client()

    if isinstance(timeseries_type, str):
        timeseries_type = TimeseriesTypeEnum(timeseries_type)

    logger.info(f"Starting NWM streamflow forecast ingestion with configuration: {nwm_configuration}, variable: {variable_name}, output type: {output_type}, timeseries type: {timeseries_type}")

    if end_dt is None:
        end_dt = datetime.now(UTC).replace(tzinfo=None)
    elif isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        update_configs={
            "spark.sql.shuffle.partitions": "4"
        }
    )

    # Format the NWM configuration name for TEEHR
    teehr_nwm_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version
    )
    if num_lookback_days is None:
        logger.info(
            "No lookback days provided, determining start date from latest"
            " NWM reference time"
        )
        latest_nwm_reference_time = ev.spark.sql(f"""
            SELECT MAX(reference_time) as latest_reference_time
            FROM iceberg.teehr.secondary_timeseries
            WHERE configuration_name = '{teehr_nwm_config["name"]}'
        """).collect()
        if len(latest_nwm_reference_time) > 0:
            latest_nwm_reference_time = latest_nwm_reference_time[0].asDict()["latest_reference_time"]
            start_dt = latest_nwm_reference_time + timedelta(minutes=1)
        else:
            start_dt = end_dt - timedelta(days=LOOKBACK_DAYS)
    else:
        logger.info(
            f"Setting start date to {num_lookback_days} days before end date"
        )
        start_dt = end_dt - timedelta(days=num_lookback_days)

    logger.info(f"Processing NWM forecasts from {start_dt} to {end_dt}")
    # Get the NWM IDs for the correct domain based on the configuration name and prefix.
    filtered_crosswalks_sdf = _filter_crosswalk_table(
        ev=ev,
        configuration_name=teehr_nwm_config["name"],
        location_id_prefix=LOCATION_ID_PREFIX
    )
    stripped_ids = [
        row[0].split("-")[1]
        for row in filtered_crosswalks_sdf.select("secondary_location_id").collect()
    ]
    logger.info(f"Found {len(stripped_ids)} location IDs after filtering for the domain and NWM sites")

    if "hawaii" in nwm_configuration:
        variable_mapper = NWM_HAWAII_VARIABLE_MAPPER
    else:
        variable_mapper = NWM_VARIABLE_MAPPER
    ev_variable_name = variable_mapper[VARIABLE_NAME].get(
        variable_name, variable_name
    )
    ev_config = format_nwm_configuration_metadata(
        nwm_config_name=nwm_configuration,
        nwm_version=nwm_version
    )
    nwm_cache_dir = Path(
        ev.cache_dir,
        "fetching",
        "nwm"
    )
    kerchunk_cache_dir = Path(
        ev.cache_dir,
        "fetching",
        "kerchunk"
    )
    # Clear out caches
    remove_dir_if_exists(nwm_cache_dir)
    remove_dir_if_exists(kerchunk_cache_dir)

    logger.info("Fetching NWM data and writing to cache")
    nwm_to_parquet(
        configuration=nwm_configuration,
        output_type=output_type,
        variable_name=variable_name,
        start_date=start_dt,
        end_date=end_dt,
        ingest_days=LOOKBACK_DAYS,
        location_ids=stripped_ids,
        json_dir=kerchunk_cache_dir,
        output_parquet_dir=Path(
            nwm_cache_dir,
            ev_config["name"],
            ev_variable_name
        ),
        nwm_version=nwm_version,
        variable_mapper=variable_mapper,
        starting_z_hour=0,
        ending_z_hour=23,
        timeseries_type=timeseries_type
    )

    # load output
    logger.info("Loading fetched data from cache into the warehouse")
    if timeseries_type == TimeseriesTypeEnum.primary:
        table_name = "primary_timeseries"
        # Need to add the NWM IDs to themselves in the crosswalk? Locations table?
        # Should the IDs just be replaced by primary in the files?
    else:
        table_name = "secondary_timeseries"
    ev._load.from_cache(
        in_path=nwm_cache_dir,
        table_name=table_name
    )
    logger.info("Successfully loaded NWM streamflow forecasts into the warehouse")
    client.close()
    ev.spark.stop()