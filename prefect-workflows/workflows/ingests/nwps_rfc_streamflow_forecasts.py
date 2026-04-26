from pathlib import Path
from datetime import datetime, UTC
from typing import Union
import logging

from prefect import flow, get_run_logger
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


@flow(
    flow_run_name="ingest-nwps-rfc-forecasts",
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

    # Fetch serially to avoid control-plane saturation from large fan-out.
    logger.info(
        f"Fetching {len(nwps_endpoints)} NWPS RFC forecasts serially"
    )

    successful = 0
    failed = 0
    total = len(nwps_endpoints)

    for idx, endpoint in enumerate(nwps_endpoints, start=1):
        try:
            result = fetch_nwps_rfc_fcst_to_cache(
                endpoint=endpoint,
                output_cache_dir=output_cache_dir,
                field_mapping=FIELD_MAPPING,
                units_mapping=UNITS_MAPPING,
                variable_names=VARIABLE_NAMES,
                configuration_name=CONFIGURATION_NAME,
                location_id_prefix=LOCATION_ID_PREFIX,
            )
            if result is None:
                # skipped due stale/empty data
                successful += 1
            else:
                successful += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            logger.error(
                f"Failed NWPS fetch task {idx}/{total} for endpoint "
                f"{endpoint.get('RFC_lid')}: {exc}"
            )
        if idx % 100 == 0:
            logger.info(
                f"NWPS fetch progress: processed={idx}/{total}, "
                f"successful={successful}, failed={failed}"
            )

    logger.info(
        f"✅ Completed fetching NWPS RFC forecast data: "
        f"successful={successful}, failed={failed}"
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
