from typing import List, Union
from datetime import datetime
from pathlib import Path

import teehr
from teehr.fetching.usgs.usgs import usgs_to_parquet
from teehr.models.fetching.utils import (
    USGSChunkByEnum,
    USGSServiceEnum,
)

from prefect import task, get_run_logger


# @task()
# Note. Evaluation object is not serializable, gives an error
# if treated as a task but still succeeds
def get_usgs_location_ids(
    ev: teehr.Evaluation
) -> List:
    """Query the USGS location IDs from the warehouse."""
    logger = get_run_logger()
    logger.info("⏰ Querying USGS location IDs")
    locations_df = ev.locations.query(
        filters={
            "column": "id",
            "operator": "like",
            "value": "usgs-%"
        }
    ).to_pandas()
    sites = locations_df["id"].str.removeprefix("usgs-").to_list()
    logger.info(f"✅ Retrieved {len(sites)} USGS location IDs")
    return sites


@task(
    timeout_seconds=60 * 5,
    retries=2
)
def fetch_usgs_data_to_cache(
    usgs_sites: List,
    output_parquet_dir: Union[str, Path],
    start_date: datetime,
    end_date: datetime,
    service: USGSServiceEnum,
    chunk_by: Union[USGSChunkByEnum, None],
    filter_to_hourly: bool,
    filter_no_data: bool,
    convert_to_si: bool,
    overwrite_output: bool,
) -> None:
    """Fetch USGS data and store in cache directory."""
    logger = get_run_logger()
    logger.info(f"⏰ Fetching USGS data from {start_date} to {end_date}")
    usgs_to_parquet(
        sites=usgs_sites,
        start_date=start_date,
        end_date=end_date,
        output_parquet_dir=output_parquet_dir,
        service=service,
        chunk_by=chunk_by,
        filter_to_hourly=filter_to_hourly,
        filter_no_data=filter_no_data,
        convert_to_si=convert_to_si,
        overwrite_output=overwrite_output
    )
