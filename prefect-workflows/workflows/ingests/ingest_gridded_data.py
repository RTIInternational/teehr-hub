import logging
from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from datetime import datetime, timedelta
import time

import icechunk as ic
from teehr_icechunk import grid_utils as gu
from teehr_icechunk import ingest, ref_ingest
from teehr_icechunk import time_grid as tg
from teehr_icechunk.prefect import runner
from teehr_icechunk.repo_const import DATA_GROUP_PATH, REFERENCES_GROUP_PATH
from teehr_icechunk.sources import ReferenceSource
from workflows.models.ingest_gridded_data_input import IngestGriddedDataInput
from workflows.utils.teehr_mapping import record_teehr_attrs
from workflows.utils.time_utils import to_naive_utc
from build_overviews import build_overviews as build_overviews_flow
from process_gridded_segment import CHILD_DEPLOYMENT

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)

configure_icechunk_s3_repo = task(gu.configure_icechunk_s3_repo, cache_policy=NO_CACHE)
write_references = task(ingest.write_references, cache_policy=NO_CACHE)
# Retried because reading source chunks can drop connections; each shard batch is committed on its own
materialize_references = task(ingest.materialize_references, cache_policy=NO_CACHE, retries=3, retry_delay_seconds=30)
open_reference_repo = task(ref_ingest.open_repo, cache_policy=NO_CACHE)
ingest_segment_references = task(ref_ingest.ingest_references, cache_policy=NO_CACHE)


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=3 * 60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data from a source over a date range into an IceChunk S3 repository.

    The source decides the repo's shape: analysis sources have one step per valid time, forecast
    sources one step per (cycle, [member], lead). Every step has a slot on the repo's time
    grid, so they can be written in any order and rewritten. Up to three stages run: source files to ``/references`` (the steps ``write_mode``
    selects), ``/references`` to ``/data`` (unless ``write_materialized`` is False), and the data
    group to the map overviews. Each later stage processes the steps its upstream group changed, so a
    run that failed part-way is completed by the next one.

    References of reference sources (GRIB2 indexes, parsed NWM analysis files) and every repo's overviews run on
    teehr-icechunk's run model: in segments, in this run or fanned out as child runs (``max_child_runs``).

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    source = args.source
    end_dt = to_naive_utc(args.end_dt)
    start_dt = _resolve_start_dt(args, end_dt)

    if isinstance(source, ReferenceSource) and source.uses_run_model():
        repo = open_reference_repo(args)
        ingest_segment_references(args, start_dt, end_dt, runner=runner(args, CHILD_DEPLOYMENT), segment_steps=args.segment_steps,
                               repo=repo)
    else:
        repo = _ingest_parsed_references(args, start_dt, end_dt)
    if args.write_materialized:
        materialize_references(repo, args)
    # Readers switch only once the group is complete; a repo can also change mode with no new files
    ingest.record_data_group(repo, DATA_GROUP_PATH if args.write_materialized else REFERENCES_GROUP_PATH)
    if args.build_overviews_on_ingest:
        build_overviews_flow(args)
    # Last, so every group (including new overview levels) gets them; also stamps repos written before
    record_teehr_attrs(repo, source.teehr_mappings())


def _ingest_parsed_references(args: IngestGriddedDataInput, start_dt: datetime, end_dt: datetime) -> ic.Repository:
    """References from parsing each listed file (HDF5, Zarr, GeoTIFF) into ``/references``; returns the repo."""
    logger = get_run_logger()
    source = args.source
    credentials = source.credentials()
    repo = configure_icechunk_s3_repo(
        source.source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        vc_credentials_kwargs=credentials,
        vc_store_kwargs=source.virtual_store_kwargs,
        **args.s3_storage_kwargs
    )
    listing = source.list_files(start_dt, end_dt)
    logger.info(f"{len(listing)} file(s) published for {args.configuration_name} from {start_dt} to {end_dt}.")
    origin = source.time_origin()
    tg.check_on_grid(listing.index.get_level_values(args.append_dim), origin, source.time_step)

    stored = tg.read_step_metadata(repo.readonly_session("main").store, REFERENCES_GROUP_PATH, args.append_dim)
    todo = tg.select_source_steps(listing, stored, args.write_mode)
    logger.info(f"{len(todo)} step(s) to write in '{args.write_mode}' mode.")
    if len(todo):
        started = time.perf_counter()
        blocks = ingest.virtual_blocks(todo, source, credentials, args)
        write_references(repo, blocks, todo, origin, source, args)
        logger.info(f"Parsed and wrote references for {len(todo)} step(s) in {time.perf_counter() - started:.1f}s.")
    return repo


def _resolve_start_dt(args: IngestGriddedDataInput, end_dt: datetime) -> datetime:
    """Start from start_dt, else the lookback window before end_dt."""
    if args.start_dt is not None:
        return to_naive_utc(args.start_dt)
    if args.num_lookback_days is not None:
        return end_dt - timedelta(days=args.num_lookback_days)
    raise ValueError("Set start_dt or num_lookback_days.")
