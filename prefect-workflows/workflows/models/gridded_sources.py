"""Gridded data sources for the ingest_gridded_data Prefect flow, selected by their ``type``."""
import re
from abc import ABC, abstractmethod
from datetime import datetime
from functools import partial
from typing import ClassVar, Literal, Optional

import numpy as np
import obstore
import pandas as pd
import xarray as xr
from obspec_utils.readers import BlockStoreReader
from obstore.store import from_url
from pydantic import BaseModel, Field, model_validator
from teehr.fetching.const import (
    NWM12_START_DATE,
    NWM20_START_DATE,
    NWM21_START_DATE,
    NWM30_START_DATE,
    NWM31_START_DATE,
)
from teehr.fetching.nwm.nwm_grids import plan_nwm_grid_fetch
from teehr.fetching.utils import REMOTE_RETRY_CONFIG, format_nwm_configuration_metadata

from workflows.utils.data_status import with_status
from workflows.utils.repo_const import LEAD_TIME, MEMBER, REFERENCE_TIME, STATUS_COORD

# Columns of a source listing, indexed by each file's timestamp (or forecast cell)
LISTING_COLUMNS = ["url", STATUS_COORD, "last_modified"]


class GriddedSource(BaseModel, ABC):
    """A gridded source: its files, its time grid, and its IceChunk repository."""

    source_bucket: ClassVar[str]
    # Source-specific obstore kwargs; deployment obstore_kwargs override them
    store_kwargs: ClassVar[dict] = {}
    # Options for the IceChunk virtual chunk container's object store, e.g. region
    virtual_store_kwargs: ClassVar[dict] = {}
    # Source-specific kwargs for the reference parser, e.g. the HDF5 reader's block size
    parser_kwargs: ClassVar[dict] = {}
    # Ingest's write_materialized when a run doesn't set it
    materialize_by_default: ClassVar[bool] = True
    time_step: ClassVar[pd.Timedelta]

    @abstractmethod
    def list_files(self, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """Files published for the range, one per step: ``LISTING_COLUMNS`` indexed by time.

        Forecast sources index by cell, (``reference_time``, [``member``], ``lead_time``), selecting
        cycles by reference time.
        """

    @abstractmethod
    def time_origin(self) -> pd.Timestamp:
        """First step of the source's record; the repo's time grid starts here."""

    @abstractmethod
    def repository_name(self) -> str:
        """IceChunk repository (configuration) name; teehr-valid (letters, digits, underscores)."""

    @abstractmethod
    def ingest_variables(self) -> list[str]:
        """Source variables to materialize."""

    def grid_name(self) -> str:
        """Grid (CRS, pixel size, extent) the source's data is on; sources sharing a grid share a name."""
        return self.repository_name()

    def lead_times(self) -> list[int] | None:
        """Forecast lead times in hours, fixed when the repo is created; None for analysis sources."""
        return None

    def members(self) -> list[int] | None:
        """Ensemble members, fixed when the repo is created; None for sources without members."""
        return None

    def fixed_axes(self) -> dict[str, list[int]]:
        """The repo's axes after its append axis, in order; empty for analysis sources."""
        axes = {MEMBER: self.members(), LEAD_TIME: self.lead_times()}
        return {name: values for name, values in axes.items() if values is not None}

    def append_dim(self) -> str:
        """The repo's append axis: cycles for forecast sources, valid times otherwise."""
        return REFERENCE_TIME if self.lead_times() is not None else "time"

    def timeseries_type(self) -> str:
        """teehr's timeseries table for the source's values."""
        return "secondary" if self.lead_times() is not None else "primary"

    def credentials(self) -> dict:
        """Source access keys, for obstore and the virtual chunk container; empty means anonymous.

        Both take the same dict, so use keys they share: S3 ``access_key_id``, ``secret_access_key``,
        ``session_token``; GCS ``service_account_key``, ``application_credentials``, ``bearer_token``.
        Keys are read once per run, so they must outlive it.
        """
        return {}

    def preprocess(self, ds: xr.Dataset, url: str) -> xr.Dataset:
        """Adjust one file's virtual dataset before concatenation."""
        return ds


def _listing(rows: list[dict], index: tuple[str, ...] = ("time",)) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=[*index, *LISTING_COLUMNS])
    if len(index) == 1:
        return df.set_index(pd.DatetimeIndex(df.pop(index[0]), name=index[0])).sort_index()
    return df.set_index(list(index)).sort_index()


class NWMForcing(GriddedSource):
    """NWM operational analysis and forecast forcing grids, listed through teehr's grid fetch planner."""

    type: Literal["nwm"] = "nwm"
    nwm_configuration: str = Field(default="forcing_analysis_assim", description="NWM configuration, e.g. 'forcing_analysis_assim'")
    nwm_version: str = Field(default="nwm31", description="NWM version, e.g. 'nwm31'. Validated against the source files.")
    output_type: str = Field(default="forcing", description="Output component of the configuration")
    variable_name: str = Field(default="RAINRATE", description="NWM variable to ingest")
    grid: str = Field(
        default="nwm30_conus_forcing",
        description="Grid the configuration's files are on; keys the pixel coverage weights"
    )
    t_minus_hours: Optional[list[int]] = Field(
        default=[2],
        description=(
            "Analysis hours (tmXX) to ingest. tm02 is the most recent analysis for each valid hour and matches "
            "the warehouse's existing NWM forcing rows."
        ),
    )
    ignore_missing_file: bool = True
    prioritize_analysis_value_time: bool = False
    drop_overlapping_assimilation_values: bool = False
    bucket: Literal["gs://national-water-model", "s3://noaa-nwm-pds"] = Field(
        default="gs://national-water-model",
        description=(
            "Bucket to read the files from; same layout in both. s3://noaa-nwm-pds (us-east-1, 2025-01-01 "
            "onward) reads in-region with no NAT transfer cost; GCS has the full history."
        ),
    )

    # Cycle interval and lead times (hours) of each forecast configuration, CONUS. Temporary home: the
    # forecast structure of NWM configurations is to move to teehr (backlog).
    forecast_grids: ClassVar[dict[str, tuple[pd.Timedelta, list[int]]]] = {
        "forcing_short_range": (pd.Timedelta("1h"), list(range(1, 19))),
        "forcing_medium_range": (pd.Timedelta("6h"), list(range(1, 241))),
        "forcing_medium_range_blend": (pd.Timedelta("6h"), list(range(1, 241))),
    }
    # The parser reads HDF5 metadata in blocks; NWM's is scattered in small pieces, so 64 KB blocks
    # read 0.66 MB per file against 8.4 MB with the 1 MB default
    parser_kwargs: ClassVar[dict] = {"reader_factory": partial(BlockStoreReader, block_size=64 * 1024)}
    # First cycle of each version; v2.1 and v2.2 are one version in teehr
    version_start: ClassVar[dict[str, datetime]] = {
        "nwm12": NWM12_START_DATE,
        "nwm20": NWM20_START_DATE,
        "nwm21": NWM21_START_DATE,
        "nwm22": NWM21_START_DATE,
        "nwm30": NWM30_START_DATE,
        "nwm31": NWM31_START_DATE,
    }
    # nwm.<YYYYMMDD>/<configuration>/nwm.t<HH>z.<...>.tm<MM>.<domain>.nc; valid time is t<HH>z minus tm<MM>
    path_pattern: ClassVar[re.Pattern] = re.compile(r"/nwm\.(\d{8})/[^/]+/nwm\.t(\d{2})z\.[^/]*\.tm(\d{2})\.[^/.]+\.nc$")
    # nwm.<YYYYMMDD>/<configuration>/nwm.t<HH>z.<...>.f<LLL>.<domain>.nc; cycle t<HH>z, lead LLL hours
    forecast_path_pattern: ClassVar[re.Pattern] = re.compile(r"/nwm\.(\d{8})/[^/]+/nwm\.t(\d{2})z\.[^/]*\.f(\d{3})\.[^/.]+\.nc$")

    @model_validator(mode="after")
    def _supported_configuration(self) -> "NWMForcing":
        if format_nwm_configuration_metadata(self.nwm_configuration, self.nwm_version)["member"] is not None:
            raise ValueError(f"Ensemble member configurations are not supported: '{self.nwm_configuration}'.")
        if "analysis_assim" not in self.nwm_configuration and not self._is_forecast:
            raise ValueError(
                f"Unsupported configuration '{self.nwm_configuration}': an analysis one or one of {sorted(self.forecast_grids)}."
            )
        if self.nwm_version not in self.version_start:
            raise ValueError(f"Unknown nwm_version '{self.nwm_version}'; one of {sorted(self.version_start)}.")
        return self

    @property
    def _is_forecast(self) -> bool:
        return self.nwm_configuration in self.forecast_grids

    @property
    def source_bucket(self) -> str:
        return self.bucket

    @property
    def time_step(self) -> pd.Timedelta:
        # Analysis grids are hourly; a forecast's step is its cycle interval
        return self.forecast_grids[self.nwm_configuration][0] if self._is_forecast else pd.Timedelta("1h")

    @property
    def store_kwargs(self) -> dict:
        # Both buckets are public
        kwargs = {"retry_config": REMOTE_RETRY_CONFIG, "skip_signature": True}
        return {**kwargs, "region": "us-east-1"} if self.bucket.startswith("s3://") else kwargs

    @property
    def virtual_store_kwargs(self) -> dict:
        return {"region": "us-east-1"} if self.bucket.startswith("s3://") else {}

    @property
    def materialize_by_default(self) -> bool:
        # noaa-nwm-pds reads are free and in-region, so only overviews are stored; GCS reads pay NAT, so read once
        return not self.bucket.startswith("s3://")

    def list_files(self, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        """One file per hour in the range, with its last modified time from one listing per day."""
        # Same planning path as teehr's nwm_grids_to_parquet: validation, GCS listing,
        # z-hour clipping by reference time, and the NWM version check
        plan = plan_nwm_grid_fetch(
            configuration=self.nwm_configuration,
            output_type=self.output_type,
            variable_name=self.variable_name,
            nwm_version=self.nwm_version,
            start_date=start_dt,
            end_date=end_dt,
            t_minus_hours=None if self._is_forecast else self.t_minus_hours,
            ignore_missing_file=self.ignore_missing_file,
            prioritize_analysis_value_time=self.prioritize_analysis_value_time,
            drop_overlapping_assimilation_values=self.drop_overlapping_assimilation_values,
        )
        # The planner lists GCS; the same keys exist in the AWS bucket
        urls = [f"{self.source_bucket}/{f.split('://', 1)[1].split('/', 1)[1]}" for f in plan.component_paths]
        modified = self._last_modified(urls)
        rows = []
        for url in urls:
            match = (self.forecast_path_pattern if self._is_forecast else self.path_pattern).search(url)
            if match is None:
                raise ValueError(f"Unexpected NWM file name: {url}")
            day, hour, offset = match.groups()
            cycle = pd.Timestamp(day) + pd.Timedelta(hours=int(hour))
            # A forecast file is a (cycle, lead) cell; an analysis file is valid tm hours before its cycle
            key = {REFERENCE_TIME: cycle, LEAD_TIME: int(offset)} if self._is_forecast else {"time": cycle - pd.Timedelta(hours=int(offset))}
            rows.append({
                **key,
                "url": url,
                STATUS_COORD: "stable",  # NWM's operational archive has no provisional versions
                # NaT if published after the listing; upsert compares it as not newer
                "last_modified": modified.get(url, pd.NaT),
            })
        listing = _listing(rows, (REFERENCE_TIME, LEAD_TIME) if self._is_forecast else ("time",))
        if listing.index.has_duplicates:
            dupes = listing.index[listing.index.duplicated()].unique()
            raise ValueError(f"{len(dupes)} step(s) have more than one file, e.g. {dupes[0]}; check t_minus_hours.")
        return listing

    def _last_modified(self, urls: list[str]) -> dict[str, pd.Timestamp]:
        """Last modified time of each file, from one listing per day and configuration directory."""
        store = from_url(f"{self.source_bucket}/", **self.store_kwargs)
        bucket = f"{self.source_bucket}/"
        prefixes = sorted({url.removeprefix(bucket).rsplit("/", 1)[0] + "/" for url in urls})
        modified = {}
        for prefix in prefixes:
            for batch in obstore.list(store, prefix=prefix):
                for obj in batch:
                    modified[f"{bucket}{obj['path']}"] = pd.Timestamp(obj["last_modified"]).tz_convert(None)
        return modified

    def time_origin(self) -> pd.Timestamp:
        start = pd.Timestamp(self.version_start[self.nwm_version])
        if self._is_forecast:
            # The version's first cycle of this configuration
            return start.ceil(self.time_step)
        # A tmXX file of the version's first cycle is valid XX hours before it
        return start - pd.Timedelta(hours=max(self.t_minus_hours or [0]))

    def repository_name(self) -> str:
        # The teehr configuration name, e.g. nwm31_forcing_analysis_assim
        return format_nwm_configuration_metadata(self.nwm_configuration, self.nwm_version)["name"]

    def ingest_variables(self) -> list[str]:
        return [self.variable_name]

    def grid_name(self) -> str:
        return self.grid

    def lead_times(self) -> list[int] | None:
        return self.forecast_grids[self.nwm_configuration][1] if self._is_forecast else None

    def preprocess(self, ds: xr.Dataset, url: str) -> xr.Dataset:
        if not self._is_forecast:
            return with_status(ds, "stable")
        # A forecast file becomes one (cycle, lead) cell, both from its name. Its own reference_time
        # and valid time are dropped (an analysis file's reference_time is its valid time).
        day, hour, lead = self.forecast_path_pattern.search(url).groups()
        cell = {REFERENCE_TIME: [pd.Timestamp(day) + pd.Timedelta(hours=int(hour))], LEAD_TIME: np.array([int(lead)], "int32")}
        timed = [name for name in ds.data_vars if "time" in ds[name].dims]
        ds = ds.drop_vars([name for name in (REFERENCE_TIME, "time") if name in ds.variables]).isel(time=0)
        # Only the gridded variables take the cell dims; scalars such as the grid mapping stay scalar
        ds = ds.assign({name: ds[name].expand_dims(cell) for name in timed})
        return with_status(ds, "stable", dim=REFERENCE_TIME)


# One source type here; with more, use Annotated[Union[...], Field(discriminator="type")]
GriddedSourceType = NWMForcing
