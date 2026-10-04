from prefect import flow, task, get_run_logger
from prefect.cache_policies import NO_CACHE
from datetime import datetime, timedelta
from typing import Callable
import icechunk as ic
import virtualizarr as vz
from virtual_tiff import VirtualTIFF
import xarray as xr
import pandas as pd

from utils import grid_utils as gu
from workflows.models.gridded_sources import GriddedSource
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
    # IFD 0 is full resolution; overviews are rebuilt as pyramids
    ParserType.tiff: lambda: VirtualTIFF(ifd=0),
}


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data from a source over a derived date range, and write to an IceChunk S3 repository.

    Runs up to three stages, each catching up from the one before: source files to standardized
    ``/references``, ``/references`` to ``/raw_data`` (unless ``write_materialized`` is False), and
    the repo's data group to the pyramids. The data group, recorded on the repo for readers, is
    ``/raw_data`` when materialized and ``/references`` otherwise. A stage with nothing new is a
    no-op, so a run that failed part-way is completed by the next one.

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()
    source = args.source

    credentials = source.credentials()
    repo = gu.configure_icechunk_s3_repo(
        source.source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        vc_credentials_kwargs=credentials,
        vc_store_kwargs=source.virtual_store_kwargs,
        **args.s3_storage_kwargs
    )

    end_dt = to_naive_utc(args.end_dt)
    start_dt = _resolve_start_dt(repo, args, end_dt)
    logger.info(f"Ingesting {args.configuration_name} from {start_dt} to {end_dt}.")

    file_list = source.build_file_list(start_dt, end_dt)
    if len(file_list) == 0:
        raise ValueError(f"No files found for {args.configuration_name} between {start_dt} and {end_dt}.")
    logger.info(f"Attempting to ingest {len(file_list)} files.")

    obstore_kwargs = {**source.store_kwargs, **credentials, **args.obstore_kwargs}
    if credentials:
        # An unsigned request ignores the credentials
        obstore_kwargs.pop("skip_signature", None)
    registry = gu.create_objectstore_registry(source.source_bucket, **obstore_kwargs)
    virtual_ds = gu.create_virtual_xarray_dataset(
        file_list,
        registry=registry,
        parser=_PARSER_MAP[args.parser_type](),
        concat_dim=args.append_dim,
        ignore_unreadable_file=args.ignore_unreadable_file,
        preprocess=_preprocess(source, args),
        **args.xconcat_kwargs
    )
    virtual_ds = _standardize_references(gu.align_virtual_fill_values(virtual_ds), args)

    write_references(repo, virtual_ds, args)
    if args.write_materialized:
        materialize_references(repo, args)
    if args.build_pyramids_on_ingest:
        build_pyramids_flow(args)


def _preprocess(source: GriddedSource, args: IngestGriddedDataInput) -> Callable[[xr.Dataset, str], xr.Dataset]:
    """Per-file preprocessing: GeoTIFF georeferencing for TIFFs, then the source's own."""
    if args.parser_type == ParserType.tiff:
        # Only a deployment's own source_crs, not the default, stands in for a file without an EPSG code
        fallback_crs = args.source_crs if "source_crs" in args.model_fields_set else None
        return lambda ds, url: source.preprocess(gu.assign_geotiff_coords(ds, fallback_crs), url)
    return source.preprocess


def _standardize_references(ds: xr.Dataset, args: IngestGriddedDataInput) -> xr.Dataset:
    """Keep the ingested variables and one version of each step, under teehr's names and metadata."""
    ds = ds[args.variable_names]
    ds = ds.drop_duplicates(dim=args.append_dim).sortby(args.append_dim)
    return gu.standardize_and_inject_geozarr(
        ds,
        source_crs=args.source_crs,
        x_dim=args.x_dim,
        y_dim=args.y_dim,
        variable_and_unit_mapper=VARIABLE_AND_UNIT_MAPPER,
    )


def _resolve_start_dt(repo: ic.Repository, args: IngestGriddedDataInput, end_dt: datetime) -> datetime:
    """Start from start_dt or the lookback window, else from the latest stored step."""
    if args.start_dt is not None:
        return to_naive_utc(args.start_dt)
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
    """Write virtual references for steps not yet in ``/references``, and record the repo's data group."""
    logger = get_run_logger()
    session = repo.writable_session("main")
    ds = gu.new_steps(virtual_ds, session.store, REFERENCES_GROUP_PATH, args.append_dim)
    if ds is not None:
        gu.write_group(ds, session, REFERENCES_GROUP_PATH, args.append_dim, virtual=True)
    data_group = RAW_DATA_GROUP_PATH if args.write_materialized else REFERENCES_GROUP_PATH
    if not gu.write_data_group(session.store, data_group) and ds is None:
        logger.info(f"No new steps for {REFERENCES_GROUP_PATH}.")
        return
    steps = 0 if ds is None else len(ds[args.append_dim])
    snapshot_id = session.commit(f"Wrote {steps} step(s) of virtual references; data group {data_group}")
    logger.info(f"Committed virtual references: {snapshot_id}")


# Retried because reading source chunks can drop connections. Each shard's worth of steps is committed
# on its own, so a retry (or the next run) resumes after the last committed batch.
@task(cache_policy=NO_CACHE, retries=3, retry_delay_seconds=30)
def materialize_references(repo: ic.Repository, args: IngestGriddedDataInput) -> None:
    """Copy referenced steps not yet in ``/raw_data`` into it, in its own chunk/shard layout."""
    logger = get_run_logger()
    store = repo.readonly_session("main").store
    if not gu.group_contains_data(store, REFERENCES_GROUP_PATH):
        logger.info(f"No data in {REFERENCES_GROUP_PATH} to materialize.")
        return
    ds = gu.restore_grid_mapping_attrs(gu.open_zarr_group(store=store, group_path=REFERENCES_GROUP_PATH))
    # References are already standardized and de-duplicated; select only the new steps
    ds = gu.drop_existing_steps(ds, store, RAW_DATA_GROUP_PATH, args.append_dim)
    if ds is None:
        logger.info(f"No new steps for {RAW_DATA_GROUP_PATH}.")
        return
    num_steps = ds.sizes[args.append_dim]
    shard_steps = args.time_chunk_size * args.num_shard_chunks
    stored = gu.stored_steps(store, RAW_DATA_GROUP_PATH, args.append_dim)
    for start, stop in gu.batch_bounds(stored, num_steps, shard_steps):
        session = repo.writable_session("main")
        gu.write_group(
            ds.isel({args.append_dim: slice(start, stop)}),
            session,
            RAW_DATA_GROUP_PATH,
            args.append_dim,
            make_encoding=lambda d: gu.create_encoding_config(
                d,
                append_dim=args.append_dim,
                chunk_size=args.chunk_size,
                num_shard_chunks=args.num_shard_chunks,
                time_chunk_size=args.time_chunk_size,
            ),
        )
        snapshot_id = session.commit(f"Materialized {stop - start} step(s) into {RAW_DATA_GROUP_PATH}")
        logger.info(f"Committed materialized steps {start + 1}-{stop} of {num_steps}: {snapshot_id}")
