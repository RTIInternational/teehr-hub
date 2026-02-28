from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Union, Optional
import logging

from prefect import flow, get_run_logger
from prefect.futures import wait
import pandas as pd

from teehr import Configuration
from teehr.models.fetching.utils import (
    USGSChunkByEnum,
    USGSServiceEnum,
)
from teehr.models.table_enums import TableWriteEnum
from teehr.fetching.const import (
    USGS_CONFIGURATION_NAME,
    USGS_VARIABLE_MAPPER,
    VARIABLE_NAME,
)
from teehr.utils.utils import remove_dir_if_exists
from utils import usgs_utils
from workflows.utils.common_utils import initialize_evaluation

logging.getLogger("teehr").setLevel(logging.INFO)


CURRENT_DT = datetime.now(UTC).replace(tzinfo=None)
LOOKBACK_DAYS = 1
CHUNK_SIZE = 100  # Number of sites to fetch per api call


@flow(
    flow_run_name="ingest-usgs-streamflow-obs",
    timeout_seconds=60 * 60
)
def ingest_usgs_streamflow_obs(
    dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp] = CURRENT_DT,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    service: USGSServiceEnum = "iv",
    chunk_by: Union[USGSChunkByEnum, None] = "location_id",
    filter_to_hourly: bool = True,
    filter_no_data: bool = True,
    convert_to_si: bool = True,
    overwrite_output: Optional[bool] = True,
    write_mode: TableWriteEnum = "append",
    drop_duplicates: bool = True,
) -> None:
    """USGS Streamflow Ingestion from NWIS.

    Notes
    -----
    - Sets the start date as end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    - Setting chunk_by to "location_id" means that usgs data
      will be saved to the cache per location ID, eliminating overwrites.
    """
    logger = get_run_logger()

    if isinstance(end_dt, str):
        # Assumes UTC
        end_dt = datetime.fromisoformat(end_dt)

    ev = initialize_evaluation(dir_path=dir_path)

    if (
        not ev.fetch._configuration_name_exists(USGS_CONFIGURATION_NAME)
    ):
        ev.configurations.add(
            Configuration(
                name=USGS_CONFIGURATION_NAME,
                type="primary",
                description="USGS streamflow gauge observations"
            )
        )
    usgs_sites = usgs_utils.get_usgs_location_ids(ev=ev)

    # Break usgs_sites into chunks
    usgs_site_chunks = [
        usgs_sites[i:i + CHUNK_SIZE]
        for i in range(0, len(usgs_sites), CHUNK_SIZE)
    ]

    usgs_variable_name = USGS_VARIABLE_MAPPER[VARIABLE_NAME][service]
    output_parquet_dir = Path(
        ev.fetch.usgs_cache_dir,
        USGS_CONFIGURATION_NAME,
        usgs_variable_name
    )

    start_dt = end_dt - timedelta(days=num_lookback_days)

    remove_dir_if_exists(ev.fetch.usgs_cache_dir)

    site_futures = []
    for i, chunk in enumerate(usgs_site_chunks):
        future = usgs_utils.fetch_usgs_data_to_cache.submit(
            usgs_sites=chunk,
            output_parquet_dir=Path(output_parquet_dir, f"part_{i}"),
            start_date=start_dt,
            end_date=end_dt,
            service=service,
            chunk_by=chunk_by,
            filter_to_hourly=filter_to_hourly,
            filter_no_data=filter_no_data,
            convert_to_si=convert_to_si,
            overwrite_output=overwrite_output,
        )
        logger.info(f"✅ Completed fetching chunk {i+1}/{len(usgs_site_chunks)} to cache")
        site_futures.append(future)

    wait(site_futures)
    logger.info("✅ Completed fetching USGS data to cache")

    # Todo: Coalesce cache files for better write performance?

    logger.info("⏰ Loading USGS data from the cache")
    ev.load.from_cache(
        in_path=Path(ev.fetch.usgs_cache_dir),
        write_mode=write_mode,
        drop_duplicates=drop_duplicates,
        table_name="primary_timeseries",
    )
    logger.info("✅ Completed loading USGS data into the warehouse")
    ev.spark.stop()
    # cleanup_temp_teehr_dir(ev.dir_path)