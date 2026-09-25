"""Define arguments and defaults for the ingest_gridded_data Prefect flow."""
import os
from datetime import datetime
from typing import Any, Optional, Union
from enum import Enum
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from workflows.models.gridded_sources import GriddedSourceType


PYRAMID_GROUP_PATH = "/pyramids"
RAW_DATA_GROUP_PATH = "/raw_data"
REFERENCES_GROUP_PATH = "/references"
ICECHUNK_BUCKET = os.getenv("ICECHUNK_BUCKET")
ICECHUNK_PREFIX = os.getenv("ICECHUNK_PREFIX")

class ParserType(str, Enum):
    """Supported parsers for reading virtual datasets."""
    hdf = "hdf"
    zarr = "zarr"


class StorageType(str, Enum):
    """Supported storage types for incoming data."""
    http = "http"
    s3 = "s3"
    gcs = "gcs"


class PackedEncoding(BaseModel):
    """CF packing (integer dtype + scale/offset) for a pyramid variable.

    Values decode as ``stored * scale_factor + add_offset``. uint16 stores 0-65535, and with
    65535 reserved as ``_FillValue`` the range is ``add_offset`` to ``add_offset + 65534 * scale_factor``,
    in steps of ``scale_factor``: a larger scale widens the range but coarsens the steps. Pick
    ``scale_factor = (max - min) / 65534`` for the plausible range; out-of-range values are clipped.
    """

    model_config = ConfigDict(populate_by_name=True)

    dtype: str = Field(..., description="Integer dtype to store, e.g. 'uint16'")
    scale_factor: float = Field(..., description="Decoded value per stored integer step")
    add_offset: float = Field(default=0.0, description="Decoded value of a stored zero")
    fill_value: int = Field(..., alias="_FillValue", description="Stored integer marking missing values (NaN)")

    @field_validator("dtype")
    @classmethod
    def _integer_dtype(cls, v: str) -> str:
        if not np.issubdtype(np.dtype(v), np.integer):
            raise ValueError(f"dtype must be an integer type, got '{v}'")
        return v

    def to_encoding(self) -> dict[str, Any]:
        """Return the xarray encoding keys for this packing."""
        return self.model_dump(by_alias=True)


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
    time_batch_size: int = Field(
        default=6,
        gt=0,
        description="Number of time steps reprojected and written per pyramid batch. Bounds memory use when many new time steps are pending."
    )
    pyramid_encoding: dict[str, PackedEncoding] = Field(
        default={},
        description=(
            "Per-variable CF packing for pyramid levels, keyed by the stored variable name, "
            "e.g. {'rainrate_hourly_mean': {'dtype': 'uint16', 'scale_factor': 2e-6, '_FillValue': 65535}}. "
            "Values are clipped to the packed range. Applies only when a pyramid level is first created."
        )
    )


class IngestGriddedDataInput(BuildPyramidsDataInput):
    """Input parameters for the ingest_gridded_data Prefect flow.

    ``source`` selects the data source by its ``type``. Dataset fields (dims, CRS, storage,
    kwargs, ...) default to UA SWANN's values; deployments for other sources override them. The
    repository name (``configuration_name``) and ``variable_names`` are derived from the source
    and hidden from the flow's parameters.
    """

    source: GriddedSourceType = Field(
        ...,
        description="The gridded data source, e.g. {'type': 'nwm', 'nwm_configuration': 'forcing_analysis_assim'}"
    )
    configuration_name: SkipJsonSchema[Optional[str]] = None
    variable_names: SkipJsonSchema[Optional[list[str]]] = None

    # --- Core required parameters ---
    source_data_storage: StorageType = Field(
        default=StorageType.http,
        description="Storage type of the source data (e.g., 's3', 'gcs', 'local', 'http')"
    )
    end_dt: Union[str, datetime, None] = Field(
        default=None,
        description="End datetime for ingestion. Defaults to current UTC time if not provided."
    )
    num_lookback_days: Union[int, None] = Field(
        default=1,
        description="Number of days before end_dt to use as start_dt. If None, start_dt is derived from the latest value in the store."
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
    obstore_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra keyword arguments passed to obstore.store.from_url(url, **obstore_kwargs)"
    )
    xconcat_kwargs: dict[str, Any] = Field(
        default={"coords": "minimal", "compat": "override", "combine_attrs": "override"},
        description="Extra keyword arguments passed to xr.concat(datasets, dim=concat_dim, **xconcat_kwargs). Used when creating the virtual dataset from the raw data files"
    )

    @model_validator(mode="before")
    @classmethod
    def _apply_source(cls, data: Any) -> Any:
        """Derive the repository and variable names from the source."""
        if not isinstance(data, dict) or "source" not in data:
            return data
        source = _SOURCE_ADAPTER.validate_python(data["source"])
        derived = {
            "configuration_name": source.repository_name(),
            "variable_names": source.ingest_variables(),
        }
        for field, value in derived.items():
            if data.get(field) not in (None, value):
                raise ValueError(f"{field} is derived from the source as {value!r}; got {data[field]!r}.")
        return {**data, **derived, "source": source}


_SOURCE_ADAPTER = TypeAdapter(GriddedSourceType)