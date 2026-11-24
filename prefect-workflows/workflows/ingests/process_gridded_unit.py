import logging
from typing import Literal, Optional

from prefect import flow
from teehr_icechunk.prefect import run_unit

from workflows.models.ingest_gridded_data_input import BuildOverviewsDataInput, IngestGriddedDataInput

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)


@flow(
    flow_run_name="process-gridded-unit",
    timeout_seconds=3 * 60 * 60,
    retries=1,
)
def process_gridded_unit(
    args: dict,
    unit: dict,
    window: Optional[dict] = None,
    stage: Literal["references", "overviews"] = "references",
) -> None:
    """One unit of a gridded run that fans out (``max_child_runs``), started by its parent flow with ``run_deployment``.

    Writes the unit's chunks and commits them; the parent records the steps once every unit is done.

    Parameters
    ----------
    args : dict
        The parent run's parameters: an ingest's, or (overviews) an ingest's or an overview build's.
    unit : dict
        The unit's first and last append-axis slots (``start``, ``end``).
    window : dict, optional
        The ingest run's ``start`` and ``end``, which bound a references unit's steps.
    stage : str
        The unit's stage: ``references`` or ``overviews``.
    """
    model = IngestGriddedDataInput if stage == "references" else BuildOverviewsDataInput
    run_unit(model.model_validate(args), unit, window, stage)
