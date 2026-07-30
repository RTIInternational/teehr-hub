import os
from typing import Any
from enum import Enum
from pydantic import BaseModel, Field


PYRAMID_GROUP_PATH = "/pyramids"
RAW_DATA_GROUP_PATH = "/raw_data"
REFERENCES_GROUP_PATH = "/references"
ICECHUNK_BUCKET = os.environ["ICECHUNK_BUCKET"]
ICECHUNK_PREFIX = os.environ["ICECHUNK_PREFIX"]

class ParserType(str, Enum):
    """Supported parsers for reading virtual datasets."""
    hdf = "hdf"
    zarr = "zarr"


class StorageType(str, Enum):
    """Supported storage types for incoming data."""
    http = "http"
    s3 = "s3"
    gcs = "gcs"


class BaseGriddedDataInput(BaseModel):
    """Base model for gridded data analysis parameters."""

    s3_storage_kwargs: dict[str, Any] = Field(
        default={"from_env": True},
        description="Extra keyword arguments passed to ic.s3_storage(bucket, prefix, **s3_storage_kwargs). Defaults to {'from_env': True}."
    )
    configuration_name: str = Field(
        ...,
        description="IceChunk repository configuration name"
    )
    dest_bucket: str = Field(
        default=ICECHUNK_BUCKET,
        description="S3 bucket name for the destination IceChunk repository (e.g., 'ciroh-rti-public-data')"
    )
    base_prefix: str = Field(
        default=ICECHUNK_PREFIX,
        description="Base path prefix within the bucket for the IceChunk repository"
    )
    append_dim: str = Field(
        default="time",
        description="Dimension along which to append data when writing to the IceChunk repository"
    )
    chunk_size: int = Field(
        default=256,
        description="Inner chunk size applied to all non-append spatial dimensions when materializing data"
    )
    num_shard_chunks: int = Field(
        default=30,
        description="Number of inner chunks along the append dimension to group into a single shard"
    )
    # TODO: Can these just be derived?
    x_dim: str = Field(
        default="lon",
        description="Name of the x spatial dimension in the source data"
    )
    y_dim: str = Field(
        default="lat",
        description="Name of the y spatial dimension in the source data"
    )


class BuildPyramidsDataInput(BaseGriddedDataInput):
    """Input parameters for the build_geozarr_pyramids Prefect flow."""

    source_crs: str = Field(
        default="EPSG:4269",
        description="Source CRS of the input data"
    )
    target_crs: str = Field(
        default="EPSG:3857",
        description="Target CRS for reprojection prior to pyramid creation"
    )
    factors: list[int] = Field(
        default=[1, 2, 4],
        description="Downsampling factors for pyramid levels. Defaults are 1, 2, 4. The number of levels is determined by the length of this list."
    )
    pyramid_method: str = Field(
        default="mean",
        description="Aggregation method for pyramid downsampling ('mean', 'max', 'min', 'sum')"
    )


class IngestGriddedDataInput(BuildPyramidsDataInput):
    """Input parameters for the ingest_gridded_data Prefect flow."""

    # --- Core required parameters ---
    source_data_storage: StorageType = Field(
        default=StorageType.http,
        description="Storage type of the source data (e.g., 's3', 'gcs', 'local', 'http')"
    )
    glob_pattern: str = Field(
        ...,
        description="Glob pattern used to match files for ingestion"
    )
    source_bucket: str = Field(
        ...,
        description="Bucket or base URL for the source data files passed to the ObjectStoreRegistry (e.g., 'https://climate.arizona.edu')"
    )
    variable_names: list[str] = Field(
        default=["SWE", "DEPTH"],
        description="Names of the variables attempt to ingest. Defaults are 'SWE', 'DEPTH'."
    )
    write_materialized: bool = Field(
        default=True,
        description="If True, the virtual datasets are materialized and written to the repository"
    )
    parser_type: ParserType = Field(
        default=ParserType.hdf,
        description="Parser to use for reading raw data files"
    )
    build_pyramids_on_ingest: bool = Field(
        default=True,
        description="If True, build and write multiscale pyramids after materializing data"
    )

    # --- Per-component extra kwargs ---
    fsspec_kwargs: dict[str, Any] = Field(
        ...,
        description="Extra keyword arguments passed to fsspec.filesystem(filesystem, **fsspec_kwargs)"
    )
    obstore_kwargs: dict[str, Any] = Field(
        ...,
        description="Extra keyword arguments passed to obstore.store.from_url(url, **obstore_kwargs)"
    )
    xconcat_kwargs: dict[str, Any] = Field(
        ...,
        description="Extra keyword arguments passed to xr.concat(datasets, dim=concat_dim, **xconcat_kwargs). Used when creating the virtual dataset from the raw data files"
    )