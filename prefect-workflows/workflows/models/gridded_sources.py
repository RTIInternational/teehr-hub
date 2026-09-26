"""Gridded data sources for the ingest_gridded_data Prefect flow, selected by their ``type``."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, Literal, Optional

from pydantic import BaseModel, Field, model_validator
from teehr.fetching.nwm.nwm_grids import plan_nwm_grid_fetch
from teehr.fetching.utils import REMOTE_RETRY_CONFIG, format_nwm_configuration_metadata


class GriddedSource(BaseModel, ABC):
    """A gridded source: its files and its IceChunk repository."""

    source_bucket: ClassVar[str]
    # Source-specific obstore kwargs; deployment obstore_kwargs override them
    store_kwargs: ClassVar[dict] = {}

    @abstractmethod
    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]: ...

    @abstractmethod
    def repository_name(self) -> str:
        """IceChunk repository (configuration) name."""

    @abstractmethod
    def ingest_variables(self) -> list[str]:
        """Source variables to materialize."""


class NWMForcing(GriddedSource):
    """NWM operational grids, listed through teehr's grid fetch planner."""

    type: Literal["nwm"] = "nwm"
    nwm_configuration: str = Field(default="forcing_analysis_assim", description="NWM configuration, e.g. 'forcing_analysis_assim'")
    nwm_version: str = Field(default="nwm31", description="NWM version, e.g. 'nwm31'. Validated against the source files.")
    output_type: str = Field(default="forcing", description="Output component of the configuration")
    variable_name: str = Field(default="RAINRATE", description="NWM variable to ingest")
    t_minus_hours: Optional[list[int]] = [0]
    ignore_missing_file: bool = True
    prioritize_analysis_value_time: bool = False
    drop_overlapping_assimilation_values: bool = False

    source_bucket: ClassVar[str] = "gs://national-water-model"
    store_kwargs: ClassVar[dict] = {"retry_config": REMOTE_RETRY_CONFIG}

    @model_validator(mode="after")
    def _single_member(self) -> "NWMForcing":
        if format_nwm_configuration_metadata(self.nwm_configuration, self.nwm_version)["member"] is not None:
            raise ValueError(f"Ensemble member configurations are not supported: '{self.nwm_configuration}'.")
        return self

    def build_file_list(self, start_dt: datetime, end_dt: datetime) -> list[str]:
        # Same planning path as teehr's nwm_grids_to_parquet: validation, GCS listing,
        # z-hour clipping by reference time, and the NWM version check
        plan = plan_nwm_grid_fetch(
            configuration=self.nwm_configuration,
            output_type=self.output_type,
            variable_name=self.variable_name,
            nwm_version=self.nwm_version,
            start_date=start_dt,
            end_date=end_dt,
            t_minus_hours=self.t_minus_hours,
            ignore_missing_file=self.ignore_missing_file,
            prioritize_analysis_value_time=self.prioritize_analysis_value_time,
            drop_overlapping_assimilation_values=self.drop_overlapping_assimilation_values,
        )
        # Replace the gcs prefix with gs
        return [f.replace("gcs://", "gs://") for f in plan.component_paths]

    def repository_name(self) -> str:
        # The teehr configuration name, e.g. nwm31_forcing_analysis_assim
        return format_nwm_configuration_metadata(self.nwm_configuration, self.nwm_version)["name"]

    def ingest_variables(self) -> list[str]:
        return [self.variable_name]


# One source type here; with more, use Annotated[Union[...], Field(discriminator="type")]
GriddedSourceType = NWMForcing
