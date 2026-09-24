"""Define arguments and defaults for the initialize_evaluation Prefect flow."""
from pathlib import Path
from typing import Union, Dict
from pydantic import BaseModel, Field


class InitializeEvaluationInputs(BaseModel):
    """Base model for initializing a TEEHR evaluation."""

    temp_dir_path: Union[str, Path] = Field(
        ...,
        description="The path to the temporary directory for creating the TEEHR Evaluation"
    )
    start_spark_cluster: bool = Field(
        False,
        description="Whether to start a Spark cluster for the evaluation"
    )
    executor_instances: int = Field(
        4,
        description="The number of Spark executor instances to use"
    )
    executor_cores: int = Field(
        7,
        description="The number of cores per Spark executor"
    )
    executor_memory: str = Field(
        "50g",
        description="The amount of memory per Spark executor"
    )
    update_configs: Union[Dict[str, str], None] = Field(
        None,
        description="A dictionary of Spark configuration updates to apply"
    )
    enable_gcs: bool = Field(
        False,
        description="Whether to enable Google Cloud Storage support in Spark"
    )
    gcs_project_id: Union[str, None] = Field(
        None,
        description="The Google Cloud project ID to use if GCS support is enabled"
    )