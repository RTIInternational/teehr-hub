from pathlib import Path
from datetime import datetime, UTC
from typing import Union
import logging
import time

from prefect import flow, get_run_logger
from prefect.futures import wait
from prefect.task_runners import ThreadPoolTaskRunner
from pyspark.sql import functions as F

from workflows.utils.common_utils import initialize_evaluation
from utils.datastream_utils import (
    coalesce_cache_files,
    load_to_warehouse
)
from utils.nwps_rfc_utils import (
    query_last_reference_times,
    generate_nwps_endpoints,
    fetch_nwps_rfc_fcst_to_cache,
    has_cache_data
)
from teehr.utils.utils import remove_dir_if_exists


logging.getLogger("teehr").setLevel(logging.INFO)

LOCATION_ID_PREFIX = "nwpsrfc"

ROOT_NWPS_URL = 'https://api.water.noaa.gov'

FIELD_MAPPING = {
    "validTime": "value_time",
    "secondary": "value",
}
VARIABLE_NAMES = [
    "streamflow_hourly_inst",
    "streamflow_6hr_inst"
]
CONFIGURATION_NAME = "nwpsrfc_streamflow_forecast"
UNITS_MAPPING = {
    "streamflow_hourly_inst": "m^3/s",
    "streamflow_6hr_inst": "m^3/s"
}
TASK_RUNNER_MAX_WORKERS = 8
SUBMISSION_BATCH_SIZE = 56
SUBMISSION_GATE_SECONDS = 5
FAILURE_RATE_THRESHOLD = 0.25


@flow(
    flow_run_name="ingest-nwps-rfc-forecasts",
    task_runner=ThreadPoolTaskRunner(max_workers=TASK_RUNNER_MAX_WORKERS),
    timeout_seconds=60 * 60
)
def ingest_nwps_rfc_forecasts(
    temp_dir_path: Union[str, Path],
    start_spark_cluster: bool = False,
) -> None:
    """RFC streamflow forecast ingestion workflow."""
    logger = get_run_logger()

    # Evaluated at flow run time, not deployment time
    current_dt = datetime.now(UTC)
    logger.info(f"Processing RFC forecasts issued by: {current_dt}")

    ev = initialize_evaluation(
        temp_dir_path=temp_dir_path,
        start_spark_cluster=start_spark_cluster,
        update_configs={
            "spark.sql.shuffle.partitions": "4"
        }
    )

    # Limit secondary IDs to USGS sites that are active and have discharge data
    filtered_crosswalks_sdf = ev.location_crosswalks.add_attributes(
        attr_list=["is_active", "has_inst_discharge"]
    ).filter(
        filters=[
            {
                "column": "secondary_location_id",
                "operator": "like",
                "value": f"{LOCATION_ID_PREFIX}-%"
            },
            "is_active = 'True'",
            "has_inst_discharge = 'True'"
        ]
    ).to_sdf()
    stripped_ids = [
        row[0].split("-")[1]
        for row in filtered_crosswalks_sdf.select("secondary_location_id").collect()
    ]

    # set up single cache directory
    output_cache_dir = Path(
        ev.cache_dir,
        "fetching",
        "nwps_rfc"
    )
    remove_dir_if_exists(output_cache_dir)

    # query last reference times for all gages at once
    last_reference_times = query_last_reference_times(
        stripped_ids=stripped_ids,
        ev=ev
    )

    # assemble API endpoints
    nwps_endpoints = generate_nwps_endpoints(
        gage_ids=stripped_ids,
        root_url=ROOT_NWPS_URL,
        last_reference_times=last_reference_times
    )

    # Submit task runs in bounded batches to balance throughput and stability.
    logger.info(
        f"Fetching {len(nwps_endpoints)} NWPS RFC forecasts in batches "
        f"(batch_size={SUBMISSION_BATCH_SIZE}, max_workers={TASK_RUNNER_MAX_WORKERS}, "
        f"gate_seconds={SUBMISSION_GATE_SECONDS})"
    )

    total = len(nwps_endpoints)
    all_futures = []

    for batch_start in range(0, total, SUBMISSION_BATCH_SIZE):
        endpoint_batch = nwps_endpoints[batch_start:batch_start + SUBMISSION_BATCH_SIZE]
        batch_index = (batch_start // SUBMISSION_BATCH_SIZE) + 1

        for endpoint in endpoint_batch:
            future = fetch_nwps_rfc_fcst_to_cache.submit(
                endpoint=endpoint,
                output_cache_dir=output_cache_dir,
                field_mapping=FIELD_MAPPING,
                units_mapping=UNITS_MAPPING,
                variable_names=VARIABLE_NAMES,
                configuration_name=CONFIGURATION_NAME,
                location_id_prefix=LOCATION_ID_PREFIX,
            )
            all_futures.append(future)

        logger.info(
            f"NWPS batch {batch_index} submitted: "
            f"processed={min(batch_start + SUBMISSION_BATCH_SIZE, total)}/{total}"
        )

        # Time-gated submission: do not wait for batch completion before enqueuing next.
        if batch_start + SUBMISSION_BATCH_SIZE < total:
            time.sleep(SUBMISSION_GATE_SECONDS)

    done, not_done = wait(all_futures)
    if not_done:
        logger.warning(f"{len(not_done)} NWPS tasks still pending after final wait()")

    successful = 0
    failed = 0
    for future in done:
        if future.state.is_completed():
            successful += 1
        else:
            failed += 1

    logger.info(
        f"✅ Completed fetching NWPS RFC forecast data: "
        f"successful={successful}, failed={failed}"
    )

    failure_rate = (failed / total) if total else 0.0
    if failure_rate > FAILURE_RATE_THRESHOLD:
        raise RuntimeError(
            f"NWPS fetch failure rate exceeded threshold: "
            f"failed={failed}/{total} ({failure_rate:.1%}) > {FAILURE_RATE_THRESHOLD:.0%}"
        )

    if failed == total:
        raise RuntimeError("All NWPS fetch tasks failed!")

    if has_cache_data(output_cache_dir):
        logger.info(
            f"Adding cached data to evaluation from: {output_cache_dir}"
        )

        # load output
        load_to_warehouse(
            ev=ev,
            in_path=output_cache_dir,
            table_name="secondary_timeseries"
        )
        logger.info("✅ Completed loading NWPS RFC data into the warehouse")
    else:
        logger.info(
            "No cache data found in cache. Skipping load."
        )

    ev.spark.stop()
