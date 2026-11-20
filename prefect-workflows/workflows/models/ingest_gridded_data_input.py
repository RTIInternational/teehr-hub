"""Define arguments and defaults for the ingest_gridded_data Prefect flow."""
import os
from datetime import datetime
from typing import Any, Literal, Optional, Union
from enum import Enum
from itertools import pairwise
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from workflows.models.gridded_sources import GriddedSourceType
from workflows.models.packed_encoding import PackedEncoding


# Spatial chunk size of overview levels, about one 256 px map tile
OVERVIEW_CHUNK_SIZE = 256
ICECHUNK_BUCKET = os.getenv("ICECHUNK_BUCKET")
ICECHUNK_PREFIX = os.getenv("ICECHUNK_PREFIX")

class ParserType(str, Enum):
    """Supported parsers for reading virtual datasets."""
    hdf = "hdf"
    zarr = "zarr"
    tiff = "tiff"


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
            "holds time_chunk_size * num_shard_chunks steps; overview shards hold as many 1-step chunks. "
            "For forecasts the same applies along the lead axis: a shard is one cycle (and member) and "
            "that many leads, so a cycle's writes never touch another cycle's shards"
        )
    )
    time_chunk_size: int = Field(
        default=1,
        gt=0,
        description=(
            "Steps per inner chunk along the append dimension of /data, or leads per inner chunk for "
            "forecasts; overviews always use 1. Larger chunks speed time-series reads but slow single-step "
            "reads, and a small append rewrites a partial chunk. Lower num_shard_chunks when raising this. "
            "Applies only when /data is first created."
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
            "Number of steps (maps: one per valid time, or per forecast cycle and lead) read and written per "
            "overview batch; a multiple of the shard length (time_chunk_size * num_shard_chunks), so each shard "
            "is written once. Bounds memory use. Forecast batches hold whole shards, at least one."
        )
    )
    source: Optional[GriddedSourceType] = Field(
        default=None,
        description=(
            "The gridded data source, e.g. {'type': 'nwm'}; sets configuration_name and the overview packing. "
            "Or set configuration_name alone for a repo without a source here"
        )
    )
    configuration_name: Optional[str] = Field(
        default=None,
        description="IceChunk repository configuration name; derived from source when that is set"
    )
    overview_encoding: Optional[dict[str, PackedEncoding]] = Field(
        default=None,
        description=(
            "Per-variable CF packing for overview levels, keyed by the stored (source) variable name, in its "
            "source units, e.g. {'RAINRATE': {'dtype': 'uint16', 'max_value': 0.075, 'units': 'mm s^-1'}}. "
            "Defaults to the source's. Values are clipped to [min_value, max_value]; variables not listed are "
            "stored as float32. Applies only when an overview level is first created."
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
    def _from_source(self) -> "BuildOverviewsDataInput":
        """The repository name and overview packing from the source, unless given."""
        if self.source is not None:
            name = self.source.repository_name()
            if self.configuration_name not in (None, name):
                raise ValueError(f"configuration_name is derived from the source as {name!r}; got {self.configuration_name!r}.")
            self.configuration_name = name
        if self.configuration_name is None:
            raise ValueError("Set source, or configuration_name.")
        if self.overview_encoding is None:
            self.overview_encoding = self.source.overview_encoding() if self.source is not None else {}
        return self

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
    repository name (``configuration_name``), ``variable_names`` and ``append_dim`` are derived
    from the source and hidden from the flow's parameters.
    """

    source: GriddedSourceType = Field(
        ...,
        description="The gridded data source, e.g. {'type': 'nwm', 'nwm_configuration': 'forcing_analysis_assim'}"
    )
    configuration_name: SkipJsonSchema[Optional[str]] = None
    variable_names: SkipJsonSchema[Optional[list[str]]] = None
    append_dim: SkipJsonSchema[Optional[str]] = None

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
        """Derive the repository and variable names, the append axis, and write_materialized unless given, from the source."""
        if not isinstance(data, dict) or "source" not in data:
            return data
        source = _SOURCE_ADAPTER.validate_python(data["source"])
        derived = {
            "configuration_name": source.repository_name(),
            "variable_names": source.ingest_variables(),
            "append_dim": source.append_dim(),
        }
        for field, value in derived.items():
            if data.get(field) not in (None, value):
                raise ValueError(f"{field} is derived from the source as {value!r}; got {data[field]!r}.")
        if data.get("write_materialized") is None:
            data = {**data, "write_materialized": source.materialize_by_default}
        return {**data, **derived, "source": source}


_SOURCE_ADAPTER = TypeAdapter(GriddedSourceType)