"""Define arguments and defaults for the mean_areal Prefect flow."""
from pydantic import Field, BaseModel
from teehr.fetching.const import NWM_VARIABLE_MAPPER, UNIT_NAME, VARIABLE_NAME

from workflows.models.ingest_gridded_data_input import BaseGriddedDataInput

# teehr's NWM mapper plus the UA SWANN snow variables it doesn't cover
VARIABLE_AND_UNIT_MAPPER = {
    VARIABLE_NAME: {
        **NWM_VARIABLE_MAPPER[VARIABLE_NAME],
        "SWE": {"name": "swe_daily_mean", "long_name": "Snow Water Equivalent"},
        "DEPTH": {"name": "depth_daily_mean", "long_name": "Snow Depth"}
    },
    UNIT_NAME: {
        **NWM_VARIABLE_MAPPER[UNIT_NAME],
        "millimeters h20": {"name": "mm", "long_name": "Millimeters"},
        "millimeters snow thickness": {"name": "mm", "long_name": "Millimeters"},
    }
}


class Metadata(BaseModel):
    name: str
    long_name: str


class VariableAndUnitMapper(BaseModel):
    variable_name: dict[str, Metadata]
    unit_name: dict[str, Metadata]


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
        description="Name of variable in the gridded dataset"
    )
    variable_and_unit_mapper: VariableAndUnitMapper = Field(
        default=VARIABLE_AND_UNIT_MAPPER,
        description="Mapping of variable names and units to their corresponding metadata"
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