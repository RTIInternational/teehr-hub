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
        description=(
            "Name of variable in the gridded dataset (e.g. 'rainrate_hourly_mean'). Written under variable_name "
            "if set, else under this name, which must then be the teehr variable name"
        )
    )
    variable_name: Optional[str] = Field(
        default=None,
        description="teehr variable name to write. Defaults to grid_variable_name"
    )
    unit_name: Optional[str] = Field(
        default=None,
        description="teehr unit name to write. Defaults to the grid variable's 'units' attribute"
    )
    value_scale: float = Field(
        1.0,
        description=(
            "Applied to the mean areal values (value * value_scale + value_offset), e.g. a unit conversion from "
            "the grid's units to unit_name. Exact, since a coverage-weighted mean is linear"
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
    write_mode: Literal["insert", "append", "upsert", "replace_where"] = Field(
        "upsert",
        description=(
            "Write mode for the timeseries table, passed to ev._write.to_warehouse(). 'upsert' replaces "
            "values for steps the grid has rewritten (e.g. provisional to stable). 'replace_where' replaces each "
            "write's slice (configuration, variable, location layer, time or cycle range) without a MERGE, so "
            "reruns are idempotent and rows a rerun no longer produces are removed"
        )
    )
    backend: Literal["local", "spark"] = Field(
        "local",
        description=(
            "'local' computes batches on the Prefect pod and writes from pandas. 'spark' runs them as Spark "
            "mapInArrow tasks that write straight to the warehouse: on executors with start_spark_cluster, else "
            "in Spark local mode"
        )
    )
    task_memory_gb: float = Field(
        2.0,
        gt=0,
        description=(
            "Memory one batch may use while reading and averaging; with the grid's chunking it sets the batch "
            "size and the row bands the window is read in"
        )
    )
    executor_instances: int = Field(
        4, gt=0, description="Spark executors, with backend 'spark' and start_spark_cluster"
    )
    executor_cores: int = Field(4, gt=0, description="Cores per Spark executor")
    executor_memory: str = Field("8g", description="JVM memory per Spark executor; Python workers get their own")
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
