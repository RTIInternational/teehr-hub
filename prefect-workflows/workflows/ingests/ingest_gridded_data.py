from prefect import flow, get_run_logger
from datetime import datetime, timedelta, UTC
import icechunk as ic
from icechunk.xarray import to_icechunk
import virtualizarr as vz
import pandas as pd

from utils import grid_utils as gu
from utils.gridded_source_builders import GriddedSource, NWMForcing
from models.ingest_gridded_data_input import (
    StorageType,
    IngestGriddedDataInput,
    ParserType,
    RAW_DATA_GROUP_PATH,
    REFERENCES_GROUP_PATH
)
from build_geozarr_pyramids import build_pyramids as build_pyramids_flow
from teehr.fetching.const import NWM30_ANALYSIS_CONFIG


DEFAULT_LOOKBACK_DAYS = 1

_PARSER_MAP = {
    ParserType.hdf: vz.parsers.HDFParser,
    ParserType.zarr: vz.parsers.ZarrParser,
}

_VIRTUAL_CONTAINER_MAP = {
    StorageType.http: lambda: ic.storage.http_store(opts={}),
    StorageType.s3: lambda: ic.storage.s3_store(opts={}),
    StorageType.gcs: lambda: ic.storage.gcs_store(opts={}),
}

_FILE_LIST_BUILDER_MAP: dict[str, GriddedSource] = {
    "nwm30-forcing-analysis-assim": NWMForcing(
        configuration="forcing_analysis_assim",
        output_type="forcing",
        analysis_config_dict=NWM30_ANALYSIS_CONFIG,
    ),
}


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data for a known configuration over a derived date range, and write to an IceChunk S3 repository.

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()

    if args.configuration_name not in _FILE_LIST_BUILDER_MAP:
        valid = list(_FILE_LIST_BUILDER_MAP.keys())
        raise ValueError(
            f"Unknown configuration_name '{args.configuration_name}'. "
            f"Valid options: {valid}"
        )
    source_config = _FILE_LIST_BUILDER_MAP[args.configuration_name]
    source_bucket = source_config.source_bucket

    parser = _PARSER_MAP[args.parser_type]()
    virtual_store = _VIRTUAL_CONTAINER_MAP[args.source_data_storage]()

    # Resolve end_dt — handle all types that arrive from Prefect UI and programmatic callers
    end_dt = args.end_dt
    if end_dt is None:
        end_dt = datetime.now(UTC).replace(tzinfo=None)
    elif isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)
    elif isinstance(end_dt, pd.Timestamp):
        end_dt = end_dt.to_pydatetime().replace(tzinfo=None)
    elif end_dt.tzinfo is not None:
        end_dt = end_dt.replace(tzinfo=None)

    # Configure the IceChunk S3 repository with a virtual chunk container
    repo = gu.configure_icechunk_s3_repo(
        source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        virtual_store=virtual_store,
        **args.s3_storage_kwargs
    )
    logger.info(
        f"IceChunk S3 repo configured at: {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}."
    )

    # Determine start_dt from lookback days or latest value in store
    if args.num_lookback_days is None:
        logger.info("No lookback days provided, determining start date from latest data in store.")
        ro_session = repo.writable_session("main")
        if gu.group_contains_data(ro_session.store, RAW_DATA_GROUP_PATH):
            existing_ds = gu.open_zarr_group(store=ro_session.store, group_path=RAW_DATA_GROUP_PATH)
            latest_val = pd.Timestamp(existing_ds[args.append_dim].values.max()).to_pydatetime().replace(tzinfo=None)
            start_dt = latest_val + timedelta(days=1)
            logger.info(f"Latest {args.append_dim} in store: {latest_val}. Setting start_dt to {start_dt}.")
        else:
            start_dt = end_dt - timedelta(days=DEFAULT_LOOKBACK_DAYS)
            logger.info(f"No existing data found. Falling back to {DEFAULT_LOOKBACK_DAYS}-day lookback: start_dt={start_dt}.")
    else:
        start_dt = end_dt - timedelta(days=args.num_lookback_days)
        logger.info(f"Setting start_dt to {args.num_lookback_days} days before end_dt: start_dt={start_dt}.")

    logger.info(f"Ingesting {args.configuration_name} from {start_dt} to {end_dt}.")

    # Build the list of files for the resolved date range
    file_list = source_config.build_file_list(start_dt, end_dt)
    if len(file_list) == 0:
        logger.warning(f"No files found for {args.configuration_name} between {start_dt} and {end_dt}.")
        raise ValueError(f"No files found for {args.configuration_name} between {start_dt} and {end_dt}.")
    logger.info(f"Attempting to ingest {len(file_list)} files.")

    # Create the ObjectStoreRegistry for the source data files
    registry = gu.create_objectstore_registry(
        source_bucket,
        **args.obstore_kwargs
    )
    logger.info(
        f"ObjectStoreRegistry created for source_bucket: {source_bucket}."
    )

    # Read the data into a virtual (lazy) xarray dataset
    virtual_ds = gu.create_virtual_xarray_dataset(
        file_list,
        registry=registry,
        parser=parser,
        concat_dim=args.append_dim,
        **args.xconcat_kwargs
    )
    logger.info("Virtual xarray dataset created.")

    # append_dim is only valid when data already exists in the store.
    # On a fresh repo the root group is empty, so omit it on the first write.
    rw_session = repo.writable_session("main")
    if gu.group_contains_data(rw_session.store, REFERENCES_GROUP_PATH):
        initial_append_dim = args.append_dim
    else:
        initial_append_dim = None

    # TODO: Upsert manually (use zarr's "region" for append dim)

    # Write virtual references to the IceChunk repository
    logger.info(f"Writing virtual references.")
    rw_session = repo.writable_session("main")
    virtual_ds.vz.to_icechunk(
        rw_session.store,
        group=REFERENCES_GROUP_PATH,
        append_dim=initial_append_dim
    )
    snapshot_id = rw_session.commit(
        f"Wrote virtual references into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Wrote virtual references into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name} with snapshot ID: {snapshot_id}")

    if args.write_materialized:
        rw_session = repo.writable_session("main")  # After any commit a session is reset to read-only
        # Materialize and write the virtual chunks to the IceChunk repository
        ds = gu.open_zarr_group(
            store=rw_session.store,
            group_path=REFERENCES_GROUP_PATH
        )
        logger.info("Selecting variables to ingest from the dataset.")
        ds = ds[args.variable_names]

        logger.info(f"Dropping potential duplicates from the virtual dataset along dimension: {args.append_dim}.")
        ds = ds.drop_duplicates(dim=args.append_dim)

        ds = gu.rechunk_dataset(ds, args.append_dim, args.chunk_size)

        ds = gu.standardize_and_inject_geozarr(
            ds,
            source_crs=args.source_crs,
            x_dim=args.x_dim,
            y_dim=args.y_dim,
        )

        # Check to see if data exists
        if not gu.group_contains_data(rw_session.store, RAW_DATA_GROUP_PATH):
            encoding_config = gu.create_encoding_config(
                ds,
                append_dim=args.append_dim,
                chunk_size=args.chunk_size,
                num_shard_chunks=args.num_shard_chunks,
            )
            write_mode = "w"
            append_dim = None
        else:
            encoding_config = None
            write_mode = "a"  # append
            append_dim = args.append_dim
            existing_ds = gu.open_zarr_group(
                store=rw_session.store,
                group_path=RAW_DATA_GROUP_PATH
            )
            ds = gu.filter_for_new_data(
                incoming_ds=ds,
                existing_ds=existing_ds,
                append_dim=args.append_dim,
            )
            if ds is None:
                logger.info(f"No new data steps found in {RAW_DATA_GROUP_PATH}. Shutting down.")
                return

        logger.info(f"Writing the chunked dataset to the Icechunk repository with mode: {write_mode}.")
        ds = ds.sortby(args.append_dim)

        to_icechunk(
            ds,
            rw_session,
            mode=write_mode,  # TODO: upsert?
            group=RAW_DATA_GROUP_PATH,
            encoding=encoding_config,
            align_chunks=True,
            append_dim=append_dim
        )
        snapshot_id = rw_session.commit(
            f"Materialized and wrote {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
        )
        logger.info(f"Materialized and wrote {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name} with snapshot ID: {snapshot_id}")

    if args.build_pyramids_on_ingest:
        build_pyramids_flow(args)
        logger.info("Pyramid building subflow completed.")


