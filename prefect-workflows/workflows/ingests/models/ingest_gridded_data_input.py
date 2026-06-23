from typing import Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class ParserType(str, Enum):
    """Supported parsers for reading virtual datasets."""
    hdf = "hdf"
    zarr = "zarr"


class DataStoreType(str, Enum):
    """Supported object store types for IceChunk virtual chunk containers."""
    http = "http"
    s3 = "s3"


class IngestGriddedDataInput(BaseModel):
    """Input parameters for the ingest_gridded_data Prefect flow."""

    # --- Core required parameters ---
    filesystem: str = Field(
        ...,
        description="Filesystem type for file discovery (e.g., 's3', 'gcs', 'local', 'http')"
    )
    glob_pattern: str = Field(
        ...,
        description="Glob pattern used to match files for ingestion"
    )
    dest_bucket: str = Field(
        ...,
        description="S3 bucket name for the destination IceChunk repository (e.g., 'ciroh-rti-public-data')"
    )
    source_bucket: str = Field(
        ...,
        description="Bucket or base URL for the source data files passed to the ObjectStoreRegistry (e.g., 'https://climate.arizona.edu')"
    )
    configuration_name: str = Field(
        ...,
        description="IceChunk repository configuration name"
    )
    write_materialized: bool = Field(
        True,
        description="If True, the virtual datasets are materialized and written to the repository"
    )

    # --- Core optional parameters ---
    base_prefix: str = Field(
        "icechunk-ingests",
        description="Base path prefix within the bucket for the IceChunk repository"
    )
    concat_dim: str = Field(
        "time",
        description="Dimension along which to concatenate datasets"
    )
    parser_type: ParserType = Field(
        ParserType.hdf,
        description="Parser to use for reading raw data files"
    )
    raw_data_group: str = Field(
        "/raw_data",
        description="Group path within the IceChunk repository to write the materialized raw data into"
    )
    pyramids_data_group: str = Field(
        "/pyramids",
        description="Group path within the IceChunk repository to write the pyramids data into"
    )
    append_dim: str = Field(
        "time",
        description="Dimension along which to append data when writing to the IceChunk repository"
    )
    chunk_size: int = Field(
        512,
        description="Inner chunk size applied to all non-append spatial dimensions when materializing data"
    )
    num_shard_chunks: int = Field(
        30,
        description="Number of inner chunks along the append dimension to group into a single shard"
    )

    # --- Pyramid creation parameters ---
    build_pyramids_on_ingest: bool = Field(
        False,
        description="If True, build and write multiscale pyramids after materializing data"
    )
    x_dim: str = Field(
        "lon",
        description="Name of the x spatial dimension in the source data"
    )
    y_dim: str = Field(
        "lat",
        description="Name of the y spatial dimension in the source data"
    )
    target_crs: str = Field(
        "EPSG:3857",
        description="Target CRS for reprojection prior to pyramid creation"
    )
    factors: List[int] = Field(
        default_factory=lambda: [1, 2, 4],
        description="Downsampling factors for pyramid levels"
    )
    pyramid_method: str = Field(
        "mean",
        description="Aggregation method for pyramid downsampling ('mean', 'max', 'min', 'sum')"
    )

    data_store_type: DataStoreType = Field(
        DataStoreType.http,
        description="Object store type for the IceChunk virtual chunk container"
    )

    # --- Per-component extra kwargs ---
    fsspec_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra keyword arguments passed to fsspec.filesystem(filesystem, **fsspec_kwargs)"
    )
    obstore_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra keyword arguments passed to obstore.store.from_url(url, **obstore_kwargs)"
    )
    s3_storage_kwargs: Dict[str, Any] = Field(
        default_factory=lambda: {"from_env": True},
        description="Extra keyword arguments passed to ic.s3_storage(bucket, prefix, **s3_storage_kwargs). Defaults to {'from_env': True}."
    )
    xconcat_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extra keyword arguments passed to xr.concat(datasets, dim=concat_dim, **xconcat_kwargs). Used when creating the virtual dataset from the raw data files"
    )
