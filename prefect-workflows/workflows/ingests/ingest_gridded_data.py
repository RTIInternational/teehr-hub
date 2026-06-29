from asyncio import subprocess

from prefect import flow, get_run_logger
import icechunk as ic
from icechunk.xarray import to_icechunk
import virtualizarr as vz
import xarray as xr
import zarr

from utils import grid_utils as gu
from models.ingest_gridded_data_input import (
    StorageType,
    IngestGriddedDataInput,
    ParserType,
    RAW_DATA_GROUP_PATH,
    REFERENCES_GROUP_PATH
)
from build_geozarr_pyramids import build_pyramids as build_pyramids_flow


_PARSER_MAP = {
    ParserType.hdf: vz.parsers.HDFParser,
    ParserType.zarr: vz.parsers.ZarrParser,
}

_VIRTUAL_CONTAINER_MAP = {
    StorageType.http: lambda: ic.storage.http_store(opts={}),
    StorageType.s3: lambda: ic.storage.s3_store(opts={}),
    StorageType.gcs: lambda: ic.storage.gcs_store(opts={}),
}


@flow(
    flow_run_name="ingest-gridded-data",
    timeout_seconds=60 * 60
)
def ingest_gridded_data(args: IngestGriddedDataInput) -> None:
    """Ingest gridded data from a specified storage type and glob pattern, and configure an IceChunk S3 repository.

    Parameters
    ----------
    args : IngestGriddedDataInput
        Pydantic model containing all flow parameters. See IngestGriddedDataInput for field descriptions.
    """
    logger = get_run_logger()

    parser = _PARSER_MAP[args.parser_type]()
    virtual_store = _VIRTUAL_CONTAINER_MAP[args.source_data_storage]()

    # Create a list of files to ingest
    file_list = gu.create_file_list(args.source_data_storage, args.glob_pattern, **args.fsspec_kwargs)
    logger.info(f"Found {len(file_list)} files to ingest.")

    # Configure the IceChunk S3 repository with a virtual chunk container
    repo = gu.configure_icechunk_s3_repo(
        args.source_bucket,
        args.dest_bucket,
        prefix=f"{args.base_prefix}/{args.configuration_name}",
        virtual_store=virtual_store,
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
    rw_session = repo.writable_session("main")
    existing_root = zarr.open_group(rw_session.store, mode="r", zarr_format=3)
    if len(list(existing_root[REFERENCES_GROUP_PATH].array_keys())) == 0:
        initial_append_dim = None
    else:
        initial_append_dim = args.append_dim


    # TODO: Append, Upsert manually (use zarr's "region" for append dim)
    logger.info(f"Writing virtual references. Initial append_dim set to: {initial_append_dim}.")

    # Write virtual references to the IceChunk repository
    rw_session = repo.writable_session("main")
    virtual_ds.vz.to_icechunk(
        rw_session.store,
        group=REFERENCES_GROUP_PATH,
        append_dim=initial_append_dim
    )
    snapshot_id = rw_session.commit(
        f"Wrote virtual references for {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Wrote virtual references for {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name} with snapshot ID: {snapshot_id}")

    if args.write_materialized:
        rw_session = repo.writable_session("main")
        # Materialize and write the virtual chunks to the IceChunk repository
        ds = xr.open_zarr(
            rw_session.store,
            group=REFERENCES_GROUP_PATH,
            consolidated=False,
            decode_coords="all"  # ensure CRS is parsed
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
        existing_group = zarr.open_group(rw_session.store, mode="r", zarr_format=3)
        if len(list(existing_group[RAW_DATA_GROUP_PATH].array_keys())) == 0:
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

        logger.info(f"Writing the chunked dataset to the Icechunk repository with mode: {write_mode}.")
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


