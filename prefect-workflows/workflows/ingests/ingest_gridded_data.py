from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from datetime import datetime, timedelta
import icechunk as ic
import virtualizarr as vz
import xarray as xr
import pandas as pd

from utils import grid_utils as gu
from workflows.models.ingest_gridded_data_input import (
    IngestGriddedDataInput,
    ParserType,
    RAW_DATA_GROUP_PATH,
    REFERENCES_GROUP_PATH,
    VARIABLE_AND_UNIT_MAPPER,
)
from build_geozarr_pyramids import build_pyramids as build_pyramids_flow
from workflows.utils.time_utils import to_naive_utc


DEFAULT_LOOKBACK_DAYS = 1

_PARSER_MAP = {
    ParserType.hdf: vz.parsers.HDFParser,
    ParserType.zarr: vz.parsers.ZarrParser,
}


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data from a source over a derived date range, and write to an IceChunk S3 repository.

    Runs three stages, each catching up from the one before: source files to ``/references``,
    ``/references`` to ``/raw_data``, and ``/raw_data`` to the pyramids. A stage with nothing
    new is a no-op, so a run that failed part-way is completed by the next one.

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()
    source = args.source

    repo = gu.configure_icechunk_s3_repo(
        source.source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        **args.s3_storage_kwargs
    )

    end_dt = to_naive_utc(args.end_dt)
    start_dt = _resolve_start_dt(repo, args, end_dt)
    logger.info(f"Ingesting {args.configuration_name} from {start_dt} to {end_dt}.")

    file_list = source.build_file_list(start_dt, end_dt)
    if len(file_list) == 0:
        raise ValueError(f"No files found for {args.configuration_name} between {start_dt} and {end_dt}.")
    logger.info(f"Attempting to ingest {len(file_list)} files.")

    registry = gu.create_objectstore_registry(
        source.source_bucket,
        **{**source.store_kwargs, **args.obstore_kwargs}
    )
    virtual_ds = gu.create_virtual_xarray_dataset(
        file_list,
        registry=registry,
        parser=_PARSER_MAP[args.parser_type](),
        concat_dim=args.append_dim,
        **args.xconcat_kwargs
    )
    virtual_ds = gu.align_virtual_fill_values(virtual_ds)

    write_references(repo, virtual_ds, args)
    if args.write_materialized:
        materialize_references(repo, args)
    if args.build_pyramids_on_ingest:
        build_pyramids_flow(args)


def _resolve_start_dt(repo: ic.Repository, args: IngestGriddedDataInput, end_dt: datetime) -> datetime:
    """Start from the lookback window, or from the latest stored step when no lookback is set."""
    if args.num_lookback_days is not None:
        return end_dt - timedelta(days=args.num_lookback_days)
    store = repo.readonly_session("main").store
    if not gu.group_contains_data(store, REFERENCES_GROUP_PATH):
        return end_dt - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    # Overlap with stored steps is filtered out before writing
    existing = gu.open_zarr_group(store=store, group_path=REFERENCES_GROUP_PATH)
    return pd.Timestamp(existing[args.append_dim].values.max()).to_pydatetime().replace(tzinfo=None)


@task(cache_policy=NO_CACHE)
def write_references(repo: ic.Repository, virtual_ds: xr.Dataset, args: IngestGriddedDataInput) -> None:
    """Write virtual references for steps not yet in ``/references``."""
    logger = get_run_logger()
    session = repo.writable_session("main")
    ds = gu.new_steps(virtual_ds, session.store, REFERENCES_GROUP_PATH, args.append_dim)
    if ds is None:
        logger.info(f"No new steps for {REFERENCES_GROUP_PATH}.")
        return
    gu.write_group(ds, session, REFERENCES_GROUP_PATH, args.append_dim, virtual=True)
    snapshot_id = session.commit(f"Wrote {len(ds[args.append_dim])} step(s) of virtual references")
    logger.info(f"Committed virtual references: {snapshot_id}")


@task(cache_policy=NO_CACHE)
def materialize_references(repo: ic.Repository, args: IngestGriddedDataInput) -> None:
    """Materialize referenced steps not yet in ``/raw_data``."""
    logger = get_run_logger()
    session = repo.writable_session("main")
    if not gu.group_contains_data(session.store, REFERENCES_GROUP_PATH):
        logger.info(f"No data in {REFERENCES_GROUP_PATH} to materialize.")
        return
    ds = gu.open_zarr_group(store=session.store, group_path=REFERENCES_GROUP_PATH)
    ds = ds[args.variable_names].drop_duplicates(dim=args.append_dim)
    ds = gu.standardize_and_inject_geozarr(
        ds,
        source_crs=args.source_crs,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        variable_and_unit_mapper=VARIABLE_AND_UNIT_MAPPER,
    )
    ds = gu.new_steps(ds, session.store, RAW_DATA_GROUP_PATH, args.append_dim)
    if ds is None:
        logger.info(f"No new steps for {RAW_DATA_GROUP_PATH}.")
        return
    gu.write_group(
        ds,
        session,
        RAW_DATA_GROUP_PATH,
        args.append_dim,
        make_encoding=lambda d: gu.create_encoding_config(
            d,
            append_dim=args.append_dim,
            chunk_size=args.chunk_size,
            num_shard_chunks=args.num_shard_chunks,
        ),
    )
    snapshot_id = session.commit(f"Materialized {len(ds[args.append_dim])} step(s) into {RAW_DATA_GROUP_PATH}")
    logger.info(f"Committed materialized data: {snapshot_id}")
