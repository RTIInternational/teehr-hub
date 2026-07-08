from pydantic import Field, BaseModel

from models.ingest_gridded_data_input import BaseGriddedDataInput

VARIABLE_AND_UNIT_MAPPER = {
    "variable_name": {
        "streamflow": {"name": "streamflow_hourly_inst", "long_name": "Hourly Instantaneous Streamflow"},
        "RAINRATE": {"name": "rainrate_hourly_mean", "long_name": "Hourly Mean Rainfall Rate"},
        "T2D": {"name": "temperature_hourly_mean", "long_name": "Hourly Mean Temperature"},
        "SWE": {"name": "swe_daily_mean", "long_name": "Snow Water Equivalent"},
        "DEPTH": {"name": "depth_daily_mean", "long_name": "Snow Depth"}
    },
    "unit_name": {
        "m3 s-1": {"name": "m^3/s", "long_name": "Cubic Meters per Second"},
        "mm s^-1": {"name": "mm/s", "long_name": "Millimeters per Second"},  # NWM 3.0 forcing
        "mm s-1": {"name": "mm/s", "long_name": "Millimeters per Second"},   # NWM 2.2 forcing
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
    grid_variable_name: dict[str, str] = Field(
        ...,
        description="Name of variable in the gridded dataset"
    )
    variable_and_unit_mapper: VariableAndUnitMapper = Field(
        default_factory=lambda: VariableAndUnitMapper(**VARIABLE_AND_UNIT_MAPPER),
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


class MeanArealValuesInput(PixelCoverageWeightsInput):
    """Model for mean areal values inputs."""

    timeseries_table_name: str = Field(
        "primary_timeseries",
        description="Name of the timeseries table in the teehr warehouse to write the mean areal values to. Default is 'primary_timeseries'."
    )