import fsspec
import xarray as xr
from obstore.store import from_url
from obspec_utils.registry import ObjectStoreRegistry
from virtualizarr import open_virtual_dataset
import virtualizarr as vz
import icechunk as ic

from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE


@task(cache_policy=NO_CACHE)
def create_file_list(filesystem: str, glob_pattern: str, **kwargs) -> list:
    """Create a list of files from a filesystem and path.

    Parameters
    ----------
    filesystem : str
        The filesystem to use (e.g., "s3", "gcs", "local", "http").
    glob_pattern : str
        The glob pattern to match files.
    **kwargs : dict
        Additional keyword arguments to pass to the fsspec filesystem.
    """
    fs = fsspec.filesystem(filesystem, **kwargs)
    file_list = fs.glob(glob_pattern)
    return file_list


@task(cache_policy=NO_CACHE)
def create_objectstore_registry(bucket: str, **kwargs) -> ObjectStoreRegistry:
    """Create an ObjectStoreRegistry for a given bucket.

    Parameters
    ----------
    bucket : str
        The name of the bucket. Must contain the trailing slash (e.g., "s3://my-bucket/").
    **kwargs : dict
        Additional keyword arguments to pass to from_url.
    """
    store = from_url(bucket, **kwargs)
    registry = ObjectStoreRegistry({bucket: store})
    return registry


@task(cache_policy=NO_CACHE)
def configure_icechunk_s3_repo(
    source_bucket: str,
    dest_bucket: str,
    prefix: str,
    virtual_store: ic.storage.ObjectStoreConfig,
    **kwargs
) -> ic.repository.Repository:
    """Configure an IceChunk S3 repository with a virtual chunk container.
    
    The virtual chunk container allows virtualized writes to the repo (ie., VirtualiZarr)

    Parameters
    ----------
    source_bucket : str
        The source bucket or base URL for the virtual chunk container (e.g., "https://climate.arizona.edu").
    dest_bucket : str
        The destination S3 bucket for the IceChunk repository (e.g., "warehouse").
    prefix : str
        The prefix within the destination bucket where the data is stored.
    virtual_store : ic.storage.ObjectStoreConfig
        The virtual store configuration to use.
    **kwargs : dict
        Additional keyword arguments to pass to the s3_storage function.
    """
    logger = get_run_logger()

    storage = ic.s3_storage(
        bucket=dest_bucket,
        prefix=prefix,
        **kwargs,
    )
    logger.info(
        f"Configuring IceChunk S3 repository for bucket: {dest_bucket}, prefix: {prefix}"
    )
    if ic.Repository.exists(storage):
        config = ic.Repository.fetch_config(storage)
        if config is None:
            config = ic.config.RepositoryConfig.default()
    else:
        config = ic.config.RepositoryConfig.default()

    url_prefix = source_bucket if source_bucket.endswith("/") else f"{source_bucket}/"
    container = ic.virtual.VirtualChunkContainer(
        url_prefix=url_prefix,
        store=virtual_store
    )
    config.set_virtual_chunk_container(container)

    if ic.Repository.exists(storage):
        logger.info(f"Existing IceChunk repository found at bucket: {dest_bucket}, prefix: {prefix}. Opening repository.")
        repo = ic.Repository.open(
            storage,
            config=config,
            authorize_virtual_chunk_access={url_prefix: None}
        )
    else:
        logger.info(f"No existing IceChunk repository found at bucket: {dest_bucket}, prefix: {prefix}. Creating new repository.")
        repo = ic.Repository.create(
            storage,
            config=config,
            authorize_virtual_chunk_access={url_prefix: None}
        )
    logger.info(f"IceChunk repository configured at bucket: {dest_bucket}, prefix: {prefix}")
    return repo


@task(cache_policy=NO_CACHE)
def create_virtual_xarray_dataset(
    file_list: list,
    registry: ObjectStoreRegistry,
    parser: vz.parsers,
    concat_dim: str,
    **kwargs
) -> xr.Dataset:
    """Create a virtual xarray dataset from a list of files.

    Parameters
    ----------
    file_list : list
        A list of file paths to include in the dataset.
    registry : ObjectStoreRegistry
        The object store registry to use for accessing the files.
    parser : vz.parsers
        The parser to use for reading the files.
    concat_dim : str
        The dimension along which to concatenate the datasets.
    **kwargs : dict
        Additional keyword arguments to pass to xr.concat.
    """
    virtual_datasets = [
        open_virtual_dataset(url, registry=registry, parser=parser) for url in file_list
    ]
    virtual_ds = xr.concat(
        virtual_datasets,
        dim=concat_dim,
        **kwargs
    )
    return virtual_ds