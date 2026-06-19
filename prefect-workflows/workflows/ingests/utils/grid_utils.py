import fsspec
import xarray as xr
from obstore.store import from_url
from obspec_utils.registry import ObjectStoreRegistry
from virtualizarr import open_virtual_dataset
import icechunk as ic

from prefect import task, get_run_logger


@task()
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


@task()
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


@task()
def configure_icechunk_s3_repo(
    bucket: str,
    prefix: str,
    virtual_store: ic.storage.ObjectStoreConfig,
    create_new_repo: bool,
    **kwargs
) -> ic.S3Repository:
    """Configure an IceChunk S3 repository with a virtual chunk container.
    
    The virtual chunk container allows virtualized writes to the repo (ie., VirtualiZarr)

    Parameters
    ----------
    bucket : str
        The name of the S3 bucket. e.g., "ciroh-rti-public-data".
    prefix : str
        The prefix within the bucket where the data is stored. This should be 
        the configuration_name.
    virtual_store : ic.storage.ObjectStoreConfig
        The virtual store configuration to use.
    create_new_repo : bool
        Whether to create a new repository or open an existing one.
    **kwargs : dict
        Additional keyword arguments to pass to the s3_storage function.
    """
    storage = ic.s3_storage(
        bucket=bucket,
        prefix=prefix,
        **kwargs,
    )
    config = ic.Repository.fetch_config(storage)
    if config is None:
        config = ic.config.RepositoryConfig.default()
    container = ic.virtual.VirtualChunkContainer(
        url_prefix=bucket,
        store=virtual_store
    )
    config.set_virtual_chunk_container(container)

    if create_new_repo is True:
        repo = ic.Repository.create(
            storage,
            config=config,
            authorize_virtual_chunk_access={bucket: None}
        )
    else:
        repo = ic.Repository.open(
            storage,
            config=config,
            authorize_virtual_chunk_access={bucket: None}
        )

    return repo


@task()
def create_virtual_xarray_dataset(
    file_list: list,
    registry: ObjectStoreRegistry,
    parser: ic.parsers.Parser,
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
    parser : ic.parsers.Parser
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