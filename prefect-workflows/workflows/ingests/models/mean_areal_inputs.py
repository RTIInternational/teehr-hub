from pydantic import Field

from models.ingest_gridded_data_input import BaseGriddedDataInput


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
    variable_name_mapping: dict[str, str] = Field(
        ...,
        description="Mapping of gridded dataset variable name to teehr dataset variable name. Format: {input_field: output_field}"
    )
    domain_name: str = Field(
        ...,
        description="Name of the domain for which pixel coverage weights are being calculated"
    )
    start_spark_cluster: bool = Field(
        False,
        description="Whether to start a Spark cluster for processing"
    )