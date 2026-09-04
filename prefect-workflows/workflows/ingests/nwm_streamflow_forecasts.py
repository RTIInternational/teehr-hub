from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import logging

from prefect import flow, get_run_logger, task, unmapped
from prefect.cache_policies import NO_CACHE
from prefect.task_runners import ProcessPoolTaskRunner
import pandas as pd
import pyspark.sql as ps

from teehr import Evaluation
from teehr.fetching.nwm.nwm_points import NwmPointFetchPlan, plan_nwm_point_fetch
from teehr.fetching.nwm.point_utils import (
    build_file_chunks,
    process_chunk_of_files,
)
from teehr.utils.utils import remove_dir_if_exists
from teehr.utils.concurrency import (
    available_cpus,
    resolve_budget,
    set_concurrency,
)
from teehr.fetching.utils import (
    format_nwm_configuration_metadata,
)
from teehr.fetching.const import (
    NWM_VARIABLE_MAPPER,
    NWM_HAWAII_VARIABLE_MAPPER,
    VARIABLE_NAME
)
from teehr.fetching.models.utils import TimeseriesTypeEnum
from workflows.utils.common_utils import initialize_evaluation
from workflows.utils.time_utils import to_naive_utc

logging.getLogger("teehr").setLevel(logging.INFO)


LOOKBACK_DAYS = 1
LOCATION_ID_PREFIX = "nwm30"
OCONUS_STATE_NAMES = [
    'Northern Mariana Islands', 'Alaska', 'Hawaii', 'Guam',
    'American Samoa', 'Puerto Rico', 'Virgin Islands'
]
# Chunks are mapped as tasks, each running in its own worker process. More
# workers than the pod has cores still pays, since the work mostly waits on GCS;
# throughput flattens out around 8. Each worker peaks near 700MB. Not a flow
# parameter: the task runner is built when this module is imported, before any
# parameter exists. The io/cpu budgets below are divided by it and *are*
# settable per run, which is the knob that moves throughput.
CHUNK_TASK_WORKERS = 8
# Matches nwm_to_parquet's defaults, which this flow relied on before it mapped
# the chunks itself.
PROCESS_BY_Z_HOUR = True
STEPSIZE = 100
IGNORE_MISSING_FILE = True
OVERWRITE_OUTPUT = False
DROP_OVERLAPPING_ASSIM_VALUES = True


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


@task(cache_policy=NO_CACHE, retries=2, retry_delay_seconds=30)
def _plan_fetch(
    nwm_configuration: str,
    output_type: str,
    variable_name: str,
    nwm_version: str,
    json_dir: Union[str, Path],
    start_dt: datetime,
    end_dt: datetime,
) -> NwmPointFetchPlan:
    """List the NWM reference files this fetch needs.

    Everything before the data is touched: validating the request, listing the
    files in GCS, and resolving or building their kerchunk references. Retried
    because it is all remote calls.
    """
    logger = get_run_logger()
    plan = plan_nwm_point_fetch(
        configuration=nwm_configuration,
        output_type=output_type,
        variable_name=variable_name,
        json_dir=json_dir,
        nwm_version=nwm_version,
        start_date=start_dt,
        end_date=end_dt,
        starting_z_hour=0,
        ending_z_hour=23,
        ignore_missing_file=IGNORE_MISSING_FILE,
        drop_overlapping_assimilation_values=DROP_OVERLAPPING_ASSIM_VALUES,
    )
    logger.info(f"Resolved {len(plan.json_paths)} NWM reference files")
    return plan


@task(cache_policy=NO_CACHE, retries=2, retry_delay_seconds=30)
def _process_chunk(
    chunk: pd.DataFrame,
    plan: NwmPointFetchPlan,
    location_ids: List[str],
    output_parquet_dir: str,
    nwm_version: str,
    variable_mapper: Dict,
    timeseries_type: TimeseriesTypeEnum,
    io_per_task: int,
    cpu_per_task: int,
) -> Optional[str]:
    """Read one chunk of reference files and write its parquet file.

    Runs in its own process, so its memory is handed back when the pool shuts
    down rather than accumulating in the flow process, which still has the
    Spark load to do. Each process builds its own obstore registry, since
    connection pools cannot be shared across processes anyway.

    Safe to retry: the chunk's output is written to a temporary file and
    renamed into place, so a failed attempt leaves nothing behind.
    """
    logger = get_run_logger()
    # This worker's share of the run's budget. Set here rather than in the
    # flow, whose settings a separate process never sees.
    set_concurrency(io=io_per_task, cpu=cpu_per_task)
    logger.info(
        f"Reading {len(chunk)} files starting"
        f" {chunk.day.iloc[0]} {chunk.z_hour.iloc[0]}"
    )
    filepath = process_chunk_of_files(
        df=chunk,
        location_ids=location_ids,
        configuration=plan.configuration,
        variable_name=plan.variable_name,
        output_parquet_dir=output_parquet_dir,
        process_by_z_hour=PROCESS_BY_Z_HOUR,
        ignore_missing_file=IGNORE_MISSING_FILE,
        overwrite_output=OVERWRITE_OUTPUT,
        nwm_version=nwm_version,
        variable_mapper=variable_mapper,
        timeseries_type=timeseries_type,
        drop_overlapping_assimilation_values=DROP_OVERLAPPING_ASSIM_VALUES,
    )
    if filepath is None:
        logger.warning("Chunk produced no data")
        return None
    logger.info(f"Wrote {Path(filepath).name}")
    return str(filepath)


@flow(
    flow_run_name="ingest-nwm-streamflow-forecasts",
    timeout_seconds=60 * 60,
    task_runner=ProcessPoolTaskRunner(max_workers=CHUNK_TASK_WORKERS)
)
async def ingest_nwm_streamflow_forecasts(
    temp_dir_path: Union[str, Path],
    end_dt: Union[str, datetime, pd.Timestamp, None] = None,
    num_lookback_days: Union[int, None] = LOOKBACK_DAYS,
    nwm_configuration: str = "short_range",
    nwm_version: str = "nwm30",
    output_type: str = "channel_rt",
    variable_name: str = "streamflow",
    start_spark_cluster: bool = False,
    timeseries_type: Union[TimeseriesTypeEnum, str] = "secondary",
    io_concurrency: Optional[int] = None,
    cpu_workers: Optional[int] = None
) -> None:
    """NWM Streamflow Forecasts Ingestion.

    Parameters
    ----------
    io_concurrency : Optional[int]
        Total GCS reads in flight across all chunk tasks, divided among them.
        Defaults to teehr's own budget (48). This is the knob that responds to
        a faster network; raise it to test.
    cpu_workers : Optional[int]
        Total compute-bound calls at once, divided the same way. Defaults to
        the CPUs the pod can use. Not clamped to that, so a value above it
        deliberately oversubscribes.

    Notes
    -----
    - By default, the flow will look back one day from the current datetime.
    - If no lookback days are provided, the flow will determine the latest reference_time
      across all locations in the existing NWM forecasts data, and set the start date to one
      minute after that time.
    - If lookback days are provided, the flow will set the start date to end date
      minus the number of lookback days.
    - End date defaults to current date and time.
    - Files are grouped into chunks and each chunk is fetched by its own task,
      so chunks run concurrently, retry independently, and report separately.
    """
    try:
        logger = get_run_logger()

        if isinstance(timeseries_type, str):
            timeseries_type = TimeseriesTypeEnum(timeseries_type)

        # Set before anything fetches, so _plan_fetch's listing gets the same
        # budget as the chunk tasks. This applies to the flow process only;
        # each worker gets its divided share passed in below.
        if io_concurrency is not None or cpu_workers is not None:
            set_concurrency(io=io_concurrency, cpu=cpu_workers)

        logger.info(f"Starting NWM streamflow forecast ingestion with configuration: {nwm_configuration}, variable: {variable_name}, output type: {output_type}, timeseries type: {timeseries_type}")

        end_dt = to_naive_utc(end_dt)

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
                variable_name, {}
        ).get("name", variable_name)

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

        # Resolve which files to read, then group them into chunks.
        plan = _plan_fetch(
            nwm_configuration=nwm_configuration,
            output_type=output_type,
            variable_name=variable_name,
            nwm_version=nwm_version,
            json_dir=kerchunk_cache_dir,
            start_dt=start_dt,
            end_dt=end_dt,
        )
        chunks = build_file_chunks(
            plan.json_paths,
            process_by_z_hour=PROCESS_BY_Z_HOUR,
            stepsize=STEPSIZE
        )

        # The chunk tasks run in separate processes, so their budgets add up
        # against the same machine. Divide both, so all of them together use
        # what a single sequential fetch would have, and hand each task its
        # share to apply on its own side.
        budget = resolve_budget()
        io_per_task = max(1, budget.io // CHUNK_TASK_WORKERS)
        cpu_per_task = max(1, budget.cpu // CHUNK_TASK_WORKERS)
        # Logged so a run's own record says what it was tuned to; comparing two
        # runs from the parameters alone hides the division and the pod's size.
        logger.info(
            f"Fetching {len(plan.json_paths)} files in {len(chunks)} chunks,"
            f" {CHUNK_TASK_WORKERS} at a time. Concurrency:"
            f" io={budget.io} total ({io_per_task} per task),"
            f" cpu={budget.cpu} total ({cpu_per_task} per task),"
            f" pod has {available_cpus()} usable cpus"
        )

        output_parquet_dir = Path(
            nwm_cache_dir,
            ev_config["name"],
            ev_variable_name
        )
        # process_chunk_of_files writes into this directory but does not create
        # it, which nwm_to_parquet used to do on our behalf.
        output_parquet_dir.mkdir(parents=True, exist_ok=True)

        written = _process_chunk.map(
            chunks,
            plan=unmapped(plan),
            location_ids=unmapped(stripped_ids),
            output_parquet_dir=unmapped(str(output_parquet_dir)),
            nwm_version=unmapped(nwm_version),
            variable_mapper=unmapped(variable_mapper),
            timeseries_type=unmapped(timeseries_type),
            io_per_task=unmapped(io_per_task),
            cpu_per_task=unmapped(cpu_per_task),
        ).result()

        paths = [path for path in written if path is not None]
        logger.info(f"Wrote {len(paths)} of {len(chunks)} chunks to the cache")

        # load output
        logger.info("Loading fetched data from cache into the warehouse")
        if timeseries_type == TimeseriesTypeEnum.primary:
            # Primarily for forcing data. Make sure the basin location IDs
            # are mapped to themselves in the location crosswalks table.
            table_name = "primary_timeseries"
        else:
            table_name = "secondary_timeseries"
        ev._load.from_cache(
            in_path=nwm_cache_dir,
            table_name=table_name
        )
        logger.info("Successfully loaded NWM streamflow forecasts into the warehouse")
    finally:
        ev.spark.stop()
