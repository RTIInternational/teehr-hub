"""Define arguments and defaults for the mean_areal Prefect flow."""
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
    grid_variable_name: str = Field(
        ...,
        description="Name of variable in the gridded dataset, already the teehr variable name (e.g. 'rainrate_hourly_mean')"
    )
    domain_name: str = Field(
        ...,
        description="Name of the domain for which pixel coverage weights are being calculated"
    )
    start_spark_cluster: bool = Field(
        False,
        description="Whether to start a Spark cluster for processing"
    )
    write_mode: str = Field(
        "append",
        description=(
            "Write mode for saving the pixel coverage weights to the warehouse table. "
            "Default is 'append'. The value is passed to ev._write.to_warehouse()."
        )
    )


class MeanArealValuesInput(PixelCoverageWeightsInput):
    """Model for mean areal values inputs."""

    timeseries_table_name: str = Field(
        "primary_timeseries",
        description=(
            "Name of the timeseries table in the teehr warehouse to write the mean areal values to. "
            "Default is 'primary_timeseries'."
        )
    )