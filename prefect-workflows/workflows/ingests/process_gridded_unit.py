import logging
from prefect import flow
from teehr_icechunk.prefect import run_unit

from workflows.models.ingest_gridded_data_input import IngestGriddedDataInput

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)


@flow(
    flow_run_name="process-gridded-unit",
    timeout_seconds=3 * 60 * 60,
    retries=1,
)
def process_gridded_unit(args: IngestGriddedDataInput, unit: dict, window: dict) -> None:
    """One unit of an ingest that fans out (``max_child_runs``), started by the ingest flow with ``run_deployment``.

    Writes the unit's chunks and commits them; the ingest flow records the steps once every unit is done.

    Parameters
    ----------
    args : IngestGriddedDataInput
        The ingest run's parameters.
    unit : dict
        The unit's first and last append-axis slots (``start``, ``end``).
    window : dict
        The ingest run's ``start`` and ``end``, which bound the unit's steps.
    """
    run_unit(args, unit, window)
