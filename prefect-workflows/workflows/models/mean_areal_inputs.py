"""Define arguments and defaults for the mean_areal Prefect flow."""
from datetime import datetime
from typing import Literal, Optional, Union

from pydantic import Field

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
    start_spark_cluster: bool = Field(
        False,
        description="Whether to start a Spark cluster for processing"
    )
    write_mode: Literal["append", "upsert"] = Field(
        "append",
        description="Write mode for the pixel coverage weights table, passed to ev._write.to_warehouse()"
    )


class MeanArealValuesInput(PixelCoverageWeightsInput):
    """Model for mean areal values inputs."""

    grid_variable_name: str = Field(
        ...,
        description="Name of variable in the gridded dataset, already the teehr variable name (e.g. 'rainrate_hourly_mean')"
    )
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
    write_mode: Literal["append", "upsert"] = Field(
        "upsert",
        description=(
            "Write mode for the timeseries table, passed to ev._write.to_warehouse(). 'upsert' replaces "
            "values for steps the grid has rewritten (e.g. provisional to stable)."
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
    max_read_memory_gb: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Memory for grid batches read at once; caps the number of concurrent batches. Defaults to "
            "the memory teehr finds available"
        )
    )
    batch_workers: Optional[int] = Field(
        default=None,
        gt=0,
        description="Concurrent grid batches before the memory cap. Defaults to the available CPUs"
    )
    zarr_concurrency: Optional[int] = Field(
        default=None,
        gt=0,
        description="Concurrent chunk reads per batch (zarr async.concurrency). Defaults to the environment's"
    )
    max_rows_per_write: int = Field(
        5_000_000,
        gt=0,
        description="Rows accumulated before each warehouse write"
    )
