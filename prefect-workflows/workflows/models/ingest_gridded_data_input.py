"""Define arguments and defaults for the ingest_gridded_data Prefect flow."""
import os
from datetime import datetime
from typing import Any, Literal, Optional, Union
from enum import Enum
from itertools import pairwise
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema
from teehr.fetching.const import NWM_VARIABLE_MAPPER

from workflows.models.gridded_sources import GriddedSourceType


# Renames source variables and units to teehr's on ingest
VARIABLE_AND_UNIT_MAPPER = NWM_VARIABLE_MAPPER
# Units each teehr variable is stored in; variables not listed keep their (mapped) source units.
# Float sources are converted in /data; integer sources keep their integers with packing that decodes to these units.
VARIABLE_UNITS = {"rainrate_hourly_mean": "mm/s"}
# Linear conversions into those units: value * scale_factor + add_offset
UNIT_CONVERSIONS = {}

OVERVIEW_GROUP_PATH = "/overviews"
# Spatial chunk size of overview levels, about one 256 px map tile
OVERVIEW_CHUNK_SIZE = 256
DATA_GROUP_PATH = "/data"
REFERENCES_GROUP_PATH = "/references"
ICECHUNK_BUCKET = os.getenv("ICECHUNK_BUCKET")
ICECHUNK_PREFIX = os.getenv("ICECHUNK_PREFIX")

class ParserType(str, Enum):
    """Supported parsers for reading virtual datasets."""
    hdf = "hdf"
    zarr = "zarr"
    tiff = "tiff"


class PackedEncoding(BaseModel):
    """CF integer packing for an overview variable, derived from its plausible range.

    Maps ``min_value``-``max_value`` onto the dtype's integers, leaving one end for
    ``_FillValue``: uint16 gives 65534 steps of ``(max_value - min_value) / 65534``. A wider
    range coarsens the steps; values outside it are clipped. ``units`` states the units of the
    range and must match the variable's stored ``units`` attribute.
    """

    model_config = ConfigDict(populate_by_name=True)

    dtype: str = Field(..., description="Integer dtype to store, e.g. 'uint16'")
    max_value: float = Field(..., description="Largest plausible decoded value, in `units`")
    min_value: float = Field(default=0.0, description="Smallest plausible decoded value, in `units`")
    units: str = Field(..., description="Units of min_value and max_value, e.g. 'mm/s'; must match the variable's units")
    fill_value: Optional[int] = Field(
        default=None,
        alias="_FillValue",
        description="Stored integer marking missing values (NaN): the dtype's min or max. Defaults to its max."
    )

    @field_validator("dtype")
    @classmethod
    def _integer_dtype(cls, v: str) -> str:
        if not np.issubdtype(np.dtype(v), np.integer):
            raise ValueError(f"dtype must be an integer type, got '{v}'")
        return v

    @model_validator(mode="after")
    def _check_range(self) -> "PackedEncoding":
        info = np.iinfo(self.dtype)
        if self.fill_value is None:
            self.fill_value = int(info.max)
        if self.fill_value not in (info.min, info.max):
            raise ValueError(f"_FillValue must be the min or max of {self.dtype}, got {self.fill_value}")
        if self.max_value <= self.min_value:
            raise ValueError(f"max_value ({self.max_value}) must be greater than min_value ({self.min_value})")
        return self

    def _stored_range(self) -> tuple[int, int]:
        """Integers available for data, excluding the fill value."""
        info = np.iinfo(self.dtype)
        lo, hi = int(info.min), int(info.max)
        return (lo, hi - 1) if self.fill_value == hi else (lo + 1, hi)

    @property
    def scale_factor(self) -> float:
        lo, hi = self._stored_range()
        return (self.max_value - self.min_value) / (hi - lo)

    @property
    def add_offset(self) -> float:
        return self.min_value - self.scale_factor * self._stored_range()[0]

    def to_encoding(self) -> dict[str, Any]:
        """Return the xarray encoding keys for this packing."""
        return {
            "dtype": self.dtype,
            "scale_factor": self.scale_factor,
            "add_offset": self.add_offset,
            "_FillValue": self.fill_value,
            # zarr's own fill must match, or chunks never written read as valid data (e.g. 0 mm/s)
            "fill_value": self.fill_value,
        }


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
        default=128,
        description=(
            "Inner chunk size along each spatial dimension of /data. Smaller chunks cut the bytes a "
            "time-series read fetches; overviews use OVERVIEW_CHUNK_SIZE"
        )
    )
    num_shard_chunks: int = Field(
        default=30,
        description=(
            "Number of inner chunks along the append dimension to group into a single shard, so a shard "
            "holds time_chunk_size * num_shard_chunks steps; overview shards hold as many 1-step chunks"
        )
    )
    time_chunk_size: int = Field(
        default=1,
        gt=0,
        description=(
            "Steps per inner chunk along the append dimension of /data; overviews always use 1. Larger "
            "chunks speed time-series reads but slow single-step reads, and a small append rewrites a "
            "partial chunk. Lower num_shard_chunks when raising this. Applies only when /data is first created."
        )
    )

    # TODO: Can these just be derived?
    x_dim: str = Field(
        default="x",
        description="Name of the x spatial dimension in the source data"
    )
    y_dim: str = Field(
        default="y",
        description="Name of the y spatial dimension in the source data"
    )


class BuildOverviewsDataInput(BaseGriddedDataInput):
    """Input parameters for the build_overviews Prefect flow."""

    overview_factors: list[int] = Field(
        default=[2, 4, 8],
        description=(
            "Block sizes averaged into each overview level, e.g. [2, 4, 8] for 2x2, 4x4 and 8x8 pixels; each a "
            "multiple of the one before. Choose them so the coarsest level is about 500 pixels across. Applies only "
            "when the overviews are first created."
        )
    )
    time_batch_size: int = Field(
        default=30,
        gt=0,
        description=(
            "Number of time steps read and written per overview batch; a multiple of the shard length "
            "(time_chunk_size * num_shard_chunks), so each shard is written once. Bounds memory use."
        )
    )
    overview_encoding: dict[str, PackedEncoding] = Field(
        default={"rainrate_hourly_mean": PackedEncoding(dtype="uint16", max_value=0.075, units="mm/s")},
        description=(
            "Per-variable CF packing for overview levels, keyed by the stored variable name, "
            "e.g. {'rainrate_hourly_mean': {'dtype': 'uint16', 'max_value': 0.075, 'units': 'mm/s'}}. "
            "Values are clipped to [min_value, max_value]; variables not listed are stored as float32. "
            "Applies only when an overview level is first created."
        )
    )

    @field_validator("overview_factors")
    @classmethod
    def _nested_factors(cls, v: list[int]) -> list[int]:
        # Each level is built from the one before, so each factor must be a multiple of the previous
        if not v or any(f < 2 for f in v) or any(b <= a or b % a for a, b in pairwise(v)):
            raise ValueError(f"overview_factors must be integers of at least 2, each a multiple of the one before; got {v}")
        return v

    @model_validator(mode="after")
    def _batch_whole_shards(self) -> "BuildOverviewsDataInput":
        shard_steps = self.time_chunk_size * self.num_shard_chunks
        if self.time_batch_size % shard_steps:
            raise ValueError(f"time_batch_size ({self.time_batch_size}) must be a multiple of the shard length ({shard_steps}).")
        return self


class IngestGriddedDataInput(BuildOverviewsDataInput):
    """Input parameters for the ingest_gridded_data Prefect flow.

    ``source`` selects the data source by its ``type``. Dataset fields (dims, kwargs, ...)
    default to NWM forcing's values; deployments for other sources override them. The
    repository name (``configuration_name``) and ``variable_names`` are derived from the source
    and hidden from the flow's parameters.
    """

    source: GriddedSourceType = Field(
        ...,
        description="The gridded data source, e.g. {'type': 'nwm', 'nwm_configuration': 'forcing_analysis_assim'}"
    )
    configuration_name: SkipJsonSchema[Optional[str]] = None
    variable_names: SkipJsonSchema[Optional[list[str]]] = None

    fallback_source_crs: Optional[str] = Field(
        default=None,
        description=(
            "CRS to apply only when a source file has none of its own; a CRS in the file always takes "
            "precedence. If neither is present, the run fails."
        )
    )

    # --- Core required parameters ---
    start_dt: Union[str, datetime, None] = Field(
        default=None,
        description="Start datetime for ingestion. If provided, num_lookback_days is ignored."
    )
    end_dt: Union[str, datetime, None] = Field(
        default=None,
        description="End datetime for ingestion. Defaults to current UTC time if not provided."
    )
    num_lookback_days: Union[int, None] = Field(
        default=1,
        description="Number of days before end_dt to use as start_dt. Ignored when start_dt is given; one of the two is required."
    )
    write_mode: Literal["append", "upsert"] = Field(
        default="append",
        description=(
            "'append' writes steps not yet in the repo. 'upsert' also rewrites steps whose source file is more "
            "final (status) or newer (last modified) than what's stored."
        )
    )
    write_materialized: Optional[bool] = Field(
        default=None,
        description=(
            "If True, the references are materialized into /data, which readers use. If False, nothing "
            "is copied and readers (overviews, EDR, mean areal values) read /references directly from the source. "
            "Defaults to the source's choice: False for NWM from s3://noaa-nwm-pds, True otherwise"
        )
    )
    ignore_unreadable_file: bool = Field(
        default=True,
        description=(
            "If True, a source file that exists but can't be opened (corrupt, or a network error) is skipped. "
            "If False, it fails the run before anything is written, so a later run can fill it in order. "
            "Missing files are skipped either way."
        )
    )
    parser_type: ParserType = Field(
        default=ParserType.hdf,
        description="Parser to use for reading raw data files"
    )
    data_fill_values: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Fill value per stored variable, for integer sources whose files declare none, e.g. {'snow_class': 255}; "
            "use a value the data never takes. A source's own _FillValue takes precedence. Applies only when "
            "/data is first created."
        )
    )
    build_overviews_on_ingest: bool = Field(
        default=True,
        description="If True, build the map overviews of the data group after materializing data"
    )

    # --- Per-component extra kwargs ---
    obstore_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra keyword arguments passed to obstore.store.from_url(url, **obstore_kwargs)"
    )
    xconcat_kwargs: dict[str, Any] = Field(
        default={
            "coords": "minimal",
            "data_vars": "minimal",
            "compat": "override",
            "join": "override",
            "combine_attrs": "override",
        },
        description="Extra keyword arguments passed to xr.concat(datasets, dim=concat_dim, **xconcat_kwargs). Used when creating the virtual dataset from the raw data files"
    )

    @model_validator(mode="before")
    @classmethod
    def _apply_source(cls, data: Any) -> Any:
        """Derive the repository and variable names, and write_materialized unless given, from the source."""
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
        if data.get("write_materialized") is None:
            data = {**data, "write_materialized": source.materialize_by_default}
        return {**data, **derived, "source": source}


_SOURCE_ADAPTER = TypeAdapter(GriddedSourceType)