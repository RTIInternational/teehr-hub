"""Define arguments and defaults for the mean_areal Prefect flow."""
from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import Field
from teehr_icechunk.models import FanOutInput

from workflows.models.ingest_gridded_data_input import BaseGriddedDataInput


class PixelCoverageWeightsInput(BaseGriddedDataInput):
    """Model for pixel coverage weights inputs."""

    temp_dir_path: str = Field(
        ...,
        description="Temporary directory path for intermediate files"
    )
    location_id_prefix: str = Field(
        ...,
        description="Prefix for location IDs to filter polygons"
    )
    grid_variable_name: Optional[str] = Field(
        default=None,
        description=(
            "Variable used as the template grid; defaults to the repo's first. Weights apply to every "
            "variable on the grid"
        )
    )
    grid_name: Optional[str] = Field(
        default=None,
        description=(
            "Name of the grid the weights index (CRS, pixel size, extent), shared by every configuration "
            "on it. Defaults to the repo's grid_name attribute, else configuration_name"
        )
    )
    min_valid_coverage: float = Field(
        0.9,
        ge=0,
        le=1,
        description=(
            "Weights: minimum fraction of a polygon's area inside the grid, or the polygon is dropped. "
            "Mean areal values: minimum fraction of a polygon's in-grid area with data, or the value is "
            "dropped. Both apply, so 0.9 keeps values covering at least 81% of a polygon"
        )
    )
    write_mode: Literal["replace_where", "upsert"] = Field(
        "replace_where",
        description=(
            "Write mode for the pixel coverage weights table, passed to ev._write.to_warehouse(). 'replace_where' "
            "replaces the layer's weights on the grid, so pixels and polygons a re-created layer no longer has are "
            "removed; 'upsert' never deletes"
        )
    )


class MeanArealValuesInput(PixelCoverageWeightsInput, FanOutInput):
    """Model for mean areal values inputs.

    Segments (``segment_steps`` append-axis slots: hours of an analysis, cycles of a forecast) run in this run or
    as ``max_child_runs`` child runs at once; each stages Parquet under ``temp_dir_path`` for this run to load.
    """

    grid_variable_name: str = Field(
        ...,
        description=(
            "Name of variable in the gridded dataset, as the source names it (e.g. 'RAINRATE'). Written under "
            "its teehr name, unit and scale from its source's teehr mapping (stamped on our repos as teehr:* "
            "attributes), unless variable_name is set"
        )
    )
    variable_name: Optional[str] = Field(
        default=None,
        description="teehr variable name to write, instead of the table's; set unit_name (and value_scale) with it"
    )
    unit_name: Optional[str] = Field(
        default=None,
        description="teehr unit name to write, with variable_name"
    )
    value_scale: float = Field(
        1.0,
        description=(
            "With variable_name: applied to the mean areal values (value * value_scale + value_offset), e.g. a "
            "unit conversion from the grid's units to unit_name. Exact, since a coverage-weighted mean is linear"
        )
    )
    value_offset: float = Field(0.0, description="See value_scale")
    timeseries_table_name: str = Field(
        "secondary_timeseries",
        description=(
            "Timeseries table to write the mean areal values to; 'primary_timeseries' registers the "
            "configuration as primary, any other table as secondary"
        )
    )
    catalog_name: Optional[str] = Field(
        default=None,
        description="Catalog of the timeseries table. Defaults to the evaluation's catalog"
    )
    namespace_name: Optional[str] = Field(
        default=None,
        description="Namespace of the timeseries table. Defaults to the evaluation's namespace"
    )
    write_mode: Literal["replace_where", "upsert"] = Field(
        "replace_where",
        description=(
            "Write mode for the timeseries table, passed to ev._write.to_warehouse(). 'replace_where' replaces each "
            "write's slice (configuration, variable, location layer, time or cycle range) without a MERGE, so "
            "reruns are idempotent and rows a rerun no longer produces are removed; it commits twice (insert, then "
            "delete), so readers can briefly see both. 'upsert' merges in one commit and never deletes"
        )
    )
    task_memory_gb: float = Field(
        2.0,
        gt=0,
        description=(
            "Memory one worker process may use while reading and averaging a block; with the grid's chunking "
            "and the chunks holding weighted pixels it sets the block size"
        )
    )
    start_dt: Union[str, datetime, None] = Field(
        default=None,
        description="First grid step to compute. Defaults to the first written step."
    )
    end_dt: Union[str, datetime, None] = Field(
        default=None,
        description="Last grid step to compute. Defaults to the last written step."
    )
