from typing import Dict, Any
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

    # --- Core optional parameters ---
    base_prefix: str = Field(
        "icechunk-ingests",
        description="Base path prefix within the bucket for the IceChunk repository"
    )
    concat_dim: str = Field(
        "time",
        description="Dimension along which to concatenate virtual datasets"
    )
    parser_type: ParserType = Field(
        ParserType.hdf,
        description="Parser to use for reading data files"
    )
    create_new_repo: bool = Field(
        True,
        description="Create a new IceChunk repository; set False to open an existing one"
    )
    repo_group: str = Field(
        "/",
        description="Group path within the IceChunk repository to write the data into (e.g., '/', '/my_group')"
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
        description="Extra keyword arguments passed to xr.concat(datasets, dim=concat_dim, **xconcat_kwargs)"
    )
