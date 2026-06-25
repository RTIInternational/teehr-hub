from prefect import flow, get_run_logger
import icechunk as ic
from icechunk.xarray import to_icechunk
import virtualizarr as vz
import xarray as xr
import zarr

from utils import grid_utils as gu
from models.ingest_gridded_data_input import DataStoreType, IngestGriddedDataInput, ParserType
from build_geozarr_pyramids import build_pyramids as build_pyramids_flow


_PARSER_MAP = {
    ParserType.hdf: vz.parsers.HDFParser,
    ParserType.zarr: vz.parsers.ZarrParser,
}

_DATA_STORE_MAP = {
    DataStoreType.http: lambda: ic.storage.http_store(opts={}),
    DataStoreType.s3: lambda: ic.storage.s3_store(opts={}),
    DataStoreType.gcs: lambda: ic.storage.gcs_store(opts={}),
}


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data from a specified filesystem and glob pattern, and configure an IceChunk S3 repository.

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()

    parser = _PARSER_MAP[args.parser_type]()
    data_store = _DATA_STORE_MAP[args.data_store_type]()

    # Create a list of files to ingest
    file_list = gu.create_file_list(args.filesystem, args.glob_pattern, **args.fsspec_kwargs)
    logger.info(f"Found {len(file_list)} files to ingest.")

    # Configure the IceChunk S3 repository with a virtual chunk container
    repo = gu.configure_icechunk_s3_repo(
        args.source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        virtual_store=data_store,
        **args.s3_storage_kwargs
    )
    logger.info(
        f"IceChunk S3 repo configured at: {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}."
    )

    # Create the ObjectStoreRegistry for the source data files
    registry = gu.create_objectstore_registry(
        args.source_bucket,
        **args.obstore_kwargs
    )
    logger.info(
        f"ObjectStoreRegistry created for source_bucket: {args.source_bucket}."
    )

    # Read the data into a virtual (lazy) xarray dataset
    virtual_ds = gu.create_virtual_xarray_dataset(
        file_list,
        registry=registry,
        parser=parser,
        concat_dim=args.concat_dim,
        **args.xconcat_kwargs
    )
    logger.info("Virtual xarray dataset created.")

    # append_dim is only valid when data already exists in the store.
    # On a fresh repo the root group is empty, so omit it on the first write.
    ro_session = repo.readonly_session("main")
    try:
        existing_root = zarr.open_group(ro_session.store, mode="r", zarr_format=3)
        initial_append_dim = args.append_dim if len(existing_root) > 0 else None
    except FileNotFoundError:
        initial_append_dim = None

    # TODO: Append, Upsert manually (use zarr's "region" for append dim)

    # Write virtual references to the IceChunk repository
    session = repo.writable_session("main")
    virtual_ds.vz.to_icechunk(
        session.store,
        group="/",
        append_dim=initial_append_dim
    )
    snapshot_id = session.commit(
        f"Wrote virtual references for {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Wrote virtual references for {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name} with snapshot ID: {snapshot_id}")

    if args.write_materialized:
        session = repo.writable_session("main")
        # Materialize and write the virtual chunks to the IceChunk repository
        ds = xr.open_zarr(
            session.store,
            group="/",
            consolidated=False,
            decode_coords="all"  # ensure CRS is parsed
        )
        logger.info("Selecting variables to ingest from the dataset.")
        ds = ds[args.variable_names]

        logger.info(f"Dropping potential duplicates from the virtual dataset along dimension: {args.append_dim}.")
        ds = ds.drop_duplicates(dim=args.append_dim)

        if ds.rio.crs is None:
            logger.info(f"Assigning CRS to the dataset: {args.source_crs}.")
            ds = ds.rio.write_crs(args.source_crs)
        else:
            ds = ds.rio.write_crs(ds.rio.crs)

        ds = gu.rechunk_dataset(ds, args.append_dim, args.chunk_size)
        encoding_config = gu.create_encoding_config(
            ds,
            append_dim=args.append_dim,
            chunk_size=args.chunk_size,
            num_shard_chunks=args.num_shard_chunks,
        )

        logger.info("Writing the chunked dataset to the Icechunk repository.")
        to_icechunk(
            ds,
            session,
            mode="w",  # TODO: append, upsert
            group=args.raw_data_group,
            encoding=encoding_config,
            align_chunks=True
        )
        snapshot_id = session.commit(
            f"Materialized and wrote {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
        )
        logger.info(f"Materialized and wrote {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name} with snapshot ID: {snapshot_id}")

    if args.build_pyramids_on_ingest:
        build_pyramids_flow(args)
        logger.info("Pyramid building subflow completed.")


