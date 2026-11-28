import logging
from typing import Literal, Optional

from prefect import flow
from teehr_icechunk.prefect import run_segment

from workflows.models.ingest_gridded_data_input import BuildOverviewsDataInput, IngestGriddedDataInput

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)


@flow(
    flow_run_name="process-gridded-segment",
    timeout_seconds=3 * 60 * 60,
    retries=1,
)
def process_gridded_segment(
    args: dict,
    segment: dict,
    window: Optional[dict] = None,
    stage: Literal["references", "overviews"] = "references",
) -> None:
    """One segment of a gridded run that fans out (``max_child_runs``), started by its parent flow with ``run_deployment``.

    Writes the segment's chunks and commits them; the parent records the steps once every segment is done.

    Parameters
    ----------
    args : dict
        The parent run's parameters: an ingest's, or (overviews) an ingest's or an overview build's.
    segment : dict
        The segment's first and last append-axis slots (``start``, ``end``).
    window : dict, optional
        The ingest run's ``start`` and ``end``, which bound a references segment's steps.
    stage : str
        The segment's stage: ``references`` or ``overviews``.
    """
    model = IngestGriddedDataInput if stage == "references" else BuildOverviewsDataInput
    run_segment(model.model_validate(args), segment, window, stage)
