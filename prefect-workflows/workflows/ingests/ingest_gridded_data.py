from prefect import flow, get_run_logger
import icechunk as ic
import virtualizarr as vz

from utils import grid_utils as gu
from models.ingest_gridded_data_input import DataStoreType, IngestGriddedDataInput, ParserType


_PARSER_MAP = {
    ParserType.hdf: vz.parsers.HDFParser,
    ParserType.zarr: vz.parsers.ZarrParser,
}

_DATA_STORE_MAP = {
    DataStoreType.http: lambda: ic.storage.http_store(opts={}),
    DataStoreType.s3: lambda: ic.storage.s3_store(opts={}),
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

    # Write the virtual dataset to the IceChunk repository
    session = repo.writable_session("main")
    virtual_ds.vz.to_icechunk(
        session.store,
        group=args.repo_group
    )
    snapshot_id = session.commit(
        f"Ingested {len(file_list)} files into {args.dest_bucket}/{args.base_prefix}/{args.configuration_name}"
    )
    logger.info(f"Data ingested into IceChunk repository with snapshot ID: {snapshot_id}.")


