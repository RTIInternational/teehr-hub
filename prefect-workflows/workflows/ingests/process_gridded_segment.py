import importlib
import logging
from typing import Optional

from prefect import flow
from teehr_icechunk.prefect import run_segment

from workflows.models.ingest_gridded_data_input import BuildOverviewsDataInput, IngestGriddedDataInput

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)

# The deployment of this flow, which parents fan out to
CHILD_DEPLOYMENT = "process-gridded-segment/process-gridded-segment"


@flow(
    flow_run_name="process-gridded-segment",
    timeout_seconds=3 * 60 * 60,
    retries=1,
)
def process_gridded_segment(
    args: dict,
    segment: dict,
    window: Optional[dict] = None,
    stage: str = "references",
    staging_dir: Optional[str] = None,
) -> None:
    """One segment of a gridded run that fans out (``max_child_runs``), started by its parent flow with ``run_deployment``.

    References and overviews: writes the segment's chunks and commits them; the parent records the steps once
    every segment is done. Mean areal values: stages the segment's values under ``staging_dir`` for the parent to
    load.

    Parameters
    ----------
    args : dict
        The parent run's parameters: an ingest's, an overview build's, or a mean areal run's.
    segment : dict
        The segment's first and last append-axis slots (``start``, ``end``).
    window : dict, optional
        The ingest run's ``start`` and ``end``, which bound a references segment's steps.
    stage : str
        ``references``, ``overviews``, or the mean areal flow module that runs the segment (e.g.
        ``mean_areal_values``), through its ``run_mean_areal_segment``.
    staging_dir : str, optional
        The mean areal run's staging directory, with its weights and output schema.
    """
    if stage in ("references", "overviews"):
        model = IngestGriddedDataInput if stage == "references" else BuildOverviewsDataInput
        run_segment(model.model_validate(args), segment, window, stage)
    else:
        importlib.import_module(stage).run_mean_areal_segment(args, segment, staging_dir)
