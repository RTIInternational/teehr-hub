import fsspec
import xarray as xr
from obstore.store import from_url
from obspec_utils.registry import ObjectStoreRegistry
from virtualizarr import open_virtual_dataset, open_virtual_mfdataset
import virtualizarr as vz
import icechunk as ic
from pyproj import CRS as PyprojCRS

from prefect import task, get_run_logger
from prefect.cache_policies import NO_CACHE


@task(cache_policy=NO_CACHE)
def create_file_list(source_data_storage: str, glob_pattern: str, **kwargs) -> list:
    """Create a list of files from a source_data_storage and path.

    Parameters
    ----------
    source_data_storage : str
        The source_data_storage to use (e.g., "s3", "gcs", "local", "http").
    glob_pattern : str
        The glob pattern to match files.
    **kwargs : dict
        Additional keyword arguments to pass to the fsspec filesystem.
    """
    fs = fsspec.filesystem(source_data_storage, **kwargs)
    file_list = fs.glob(glob_pattern)
    # If source_data_storage is gcs, prepend "gs://" to each file path
    if source_data_storage == "gcs":
        file_list = [f"gs://{file}" for file in file_list]
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
    logger = get_run_logger()
    logger.info(f"Creating ObjectStoreRegistry for bucket: {bucket} and kwargs: {kwargs}")
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
    repo.save_config()
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
    if len(virtual_datasets) == 0:
        raise ValueError("No virtual datasets were created. Check the file list and registry of the source data.")
    virtual_ds = xr.concat(
        virtual_datasets,
        dim=concat_dim,
        **kwargs
    )
    # # TODO: open_mfdataset()?
    # virtual_ds = open_virtual_mfdataset(
    #     file_list,
    #     registry=registry,
    #     parser=parser,
    #     concat_dim=concat_dim,
    #     **kwargs
    # )
    return virtual_ds


@task(cache_policy=NO_CACHE)
def rechunk_dataset(
    dataset: xr.Dataset,
    append_dim: str,
    chunk_size: int,
) -> xr.Dataset:
    """Re-chunk an xarray dataset prior to writing to IceChunk.

    The append dimension (e.g. time) is chunked to 1 so that individual
    time-steps can be appended independently.  All other dimensions are
    chunked to ``chunk_size``.

    Parameters
    ----------
    dataset : xr.Dataset
        The dataset to re-chunk.
    append_dim : str
        The dimension used for appending (chunked to 1).
    chunk_size : int
        Chunk size applied to every dimension other than ``append_dim``.
    """
    chunks = {d: (1 if d == append_dim else chunk_size) for d in dataset.dims}
    return dataset.chunk(chunks)


@task(cache_policy=NO_CACHE)
def create_encoding_config(
    dataset: xr.Dataset,
    append_dim: str,
    chunk_size: int = 512,
    num_shard_chunks: int = 30,
    compression: str = "zstd",
    compression_level: int = 3,
    shuffle: str = "shuffle",
) -> dict:
    """Create an encoding configuration for writing a dataset to IceChunk.

    Data variables receive chunk/shard/compression encoding.  Non-dimension
    coordinates (e.g. ``spatial_ref`` / CRS grids) are written unchunked.

    Parameters
    ----------
    dataset : xr.Dataset
        The dataset to create encoding for.
    append_dim : str
        The dimension used for appending (e.g. "time").  Inner chunks along
        this dimension are set to 1; shards pack ``num_shard_chunks`` of them.
    chunk_size : int
        Inner chunk size for all non-append dimensions (default 512).
    num_shard_chunks : int
        Number of inner chunks to group into a single shard along ``append_dim``
        (default 30).
    compression : str
        Compression algorithm to use (default "zstd").
    compression_level : int
        Compression level (default 3).
    shuffle : str
        Whether to apply the byte-shuffle filter before compression (default "shuffle").
    """
    encoding_config = {}
    for var in dataset.data_vars:
        dims = dataset[var].dims
        chunks = tuple(1 if d == append_dim else chunk_size for d in dims)
        shards = tuple(num_shard_chunks if d == append_dim else chunk_size for d in dims)
        encoding_config[var] = {
            "chunks": chunks,
            "shards": shards,
            "compressors": {
                "name": "blosc",
                "configuration": {
                    "cname": compression,
                    "clevel": compression_level,
                    "shuffle": shuffle
                }
            }
        }
    # Non-dimension coordinates (e.g. spatial_ref/CRS) are written unchunked
    for coord in dataset.coords:
        if coord not in dataset.dims:
            encoding_config[coord] = {"chunks": None}

    return encoding_config


@task(cache_policy=NO_CACHE)
def reproject_dataset(
    dataset: xr.Dataset,
    target_crs: str,
    x_dim: str,
    y_dim: str,
    source_crs: str | None = None
) -> xr.Dataset:
    """Reproject an xarray dataset to a target CRS.

    Parameters
    ----------
    dataset : xr.Dataset
        The dataset to reproject.
    target_crs : str
        The target CRS to reproject the dataset to.
    x_dim : str
        The name of the x dimension.
    y_dim : str
        The name of the y dimension.
    source_crs : str | None
        The source CRS to use if the dataset does not have one defined.
    """
    logger = get_run_logger()
    logger.info(
        f"Reprojecting dataset to target CRS: {target_crs} and setting spatial dims: x={x_dim}, y={y_dim}."
    )
    dataset = dataset.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
    if dataset.rio.crs is None:
        logger.info(f"No CRS found in the source dataset. Assigning: {source_crs}.")
        dataset = dataset.rio.write_crs(source_crs)
    else:
        logger.info(f"Source dataset has a CRS defined: {dataset.rio.crs}.")
        dataset = dataset.rio.write_crs(dataset.rio.crs)
    ds_mercator = dataset.rio.reproject(target_crs)
    ds_mercator = ds_mercator.proj.assign_crs(spatial_ref=target_crs)
    return ds_mercator


@task(cache_policy=NO_CACHE)
def standardize_and_inject_geozarr(
    ds: xr.Dataset,
    source_crs: str | None = None,
    x_dim: str | None = None,
    y_dim: str | None = None,
) -> xr.Dataset:
    """Write CF-1.11 and GeoZarr metadata to a dataset before writing to IceChunk.

    Resolves spatial dimensions and CRS, then writes:
    - A scalar ``spatial_ref`` coordinate with CF grid mapping attrs and WKT strings.
    - CF axis/standard_name attrs on the x/y coordinate variables.
    - ``grid_mapping``, ``proj:wkt2``, and ``spatial:dimensions`` on each spatial data var.
    - ``proj:wkt2``, ``spatial:dimensions``, and ``Conventions`` on the dataset itself.
    """
    logger = get_run_logger()

    # --- Resolve spatial dimensions ---
    if x_dim and y_dim and x_dim in ds.dims and y_dim in ds.dims:
        ds = ds.rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim)
        x_name, y_name = x_dim, y_dim
    else:
        try:
            x_name, y_name = ds.rio.x_dim, ds.rio.y_dim
        except Exception:
            x_name = x_dim if x_dim in ds.dims else None
            y_name = y_dim if y_dim in ds.dims else None

    if x_name is None or y_name is None:
        raise ValueError(
            "Unable to determine spatial dimensions. "
            "Provide valid x_dim/y_dim or ensure the dataset has discoverable spatial dims."
        )

    # --- Resolve CRS ---
    crs_obj = ds.rio.crs
    if crs_obj is None:
        if source_crs is None:
            raise ValueError(
                "Dataset has no CRS and no source_crs fallback was provided."
            )
        logger.info(f"No CRS found; applying fallback: {source_crs}.")
        ds = ds.rio.write_crs(source_crs)
        crs_obj = ds.rio.crs

    wkt_string = crs_obj.to_wkt()
    pyproj_crs = PyprojCRS.from_user_input(crs_obj)

    # --- Build grid mapping coordinate attrs ---
    # Use full CF params when available (enables cf-xarray grid_mappings detection).
    # Some projected CRS (e.g. EPSG:3857 Web Mercator) don't produce a grid_mapping_name
    # from pyproj.to_cf() in all versions. grid_mapping_name must be present for
    # cf-xarray to identify the coordinate as a grid mapping variable; crs_wkt is then
    # the authoritative source that CRS.from_cf() will use to reconstruct the CRS.
    cf_params = pyproj_crs.to_cf()
    if cf_params.get("grid_mapping_name") is None:
        cf_params["grid_mapping_name"] = "mercator"
        logger.warning(
            f"CRS {pyproj_crs.to_string()} produced no CF grid_mapping_name; "
            "defaulting to 'mercator'. CRS will be reconstructed from crs_wkt."
        )
    grid_mapping_attrs = {**cf_params, "crs_wkt": wkt_string, "spatial_ref": wkt_string}

    # Reuse an existing CRS coordinate if present, otherwise use "spatial_ref".
    gm_coord = next(
        (
            c for c in ds.coords
            if any(k in ds[c].attrs for k in ("grid_mapping_name", "crs_wkt", "spatial_ref"))
        ),
        "spatial_ref",
    )
    ds = ds.assign_coords({gm_coord: xr.DataArray(0, attrs=grid_mapping_attrs)})

    # --- x/y coordinate attrs ---
    is_geographic = crs_obj.is_geographic
    if x_name in ds.coords:
        ds[x_name].attrs["axis"] = "X"
        ds[x_name].attrs.setdefault(
            "standard_name", "longitude" if is_geographic else "projection_x_coordinate"
        )
    if y_name in ds.coords:
        ds[y_name].attrs["axis"] = "Y"
        ds[y_name].attrs.setdefault(
            "standard_name", "latitude" if is_geographic else "projection_y_coordinate"
        )

    # --- Dataset-level attrs ---
    conventions = ds.attrs.get("Conventions")
    if conventions is None:
        ds.attrs["Conventions"] = "CF-1.11"
    elif "CF-" not in str(conventions):
        ds.attrs["Conventions"] = f"{conventions} CF-1.11"
    ds.attrs["proj:wkt2"] = wkt_string
    ds.attrs["spatial:dimensions"] = [y_name, x_name]

    # --- Per-variable attrs for spatial data vars ---
    for var in ds.data_vars:
        if {x_name, y_name} <= set(ds[var].dims):
            ds[var].attrs["grid_mapping"] = gm_coord
            ds[var].attrs["proj:wkt2"] = wkt_string
            ds[var].attrs["spatial:dimensions"] = [y_name, x_name]

    return ds
