"""Define arguments and defaults for the create_vector_tiles Prefect flow."""
import os
from pydantic import Field

from workflows.models.initialize_evaluation_inputs import InitializeEvaluationInputs

PMTILES_BUCKET = os.getenv("PMTILES_BUCKET")
PMTILES_PREFIX = os.getenv("PMTILES_PREFIX")

class VectorTilesInput(InitializeEvaluationInputs):
    """Base model for create vector tiles flow parameters."""

    location_id_prefix: str = Field(
        ...,
        description="The location ID prefix used to filter the locations warehouse table"
    )
    output_layer_name: str = Field(
        ...,
        description="The name of the output layer for the pmtiles archive"
    )
    target_bucket_name: str = Field(
        PMTILES_BUCKET,
        description="The name of the target S3 bucket for the pmtiles archive"
    )
    target_prefix: str = Field(
        PMTILES_PREFIX,
        description="The prefix path within the target S3 bucket for the pmtiles archive"
    )
