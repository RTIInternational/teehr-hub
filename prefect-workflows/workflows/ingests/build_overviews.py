import logging
from prefect import flow
from teehr_icechunk import overviews
from teehr_icechunk.prefect import runner

from workflows.models.ingest_gridded_data_input import BuildOverviewsDataInput

# Show the package's progress in the run logs: PREFECT_LOGGING_EXTRA_LOGGERS attaches Prefect's handlers,
# not a level, so the logger would otherwise inherit the root's WARNING
logging.getLogger("teehr_icechunk").setLevel(logging.INFO)

# Units fan out as runs of this deployment (prefect-*.yaml)
CHILD_DEPLOYMENT = "process-gridded-unit/process-gridded-unit"


@flow(
    flow_run_name="build-overviews",
    timeout_seconds=3 * 60 * 60
)
def build_overviews(args: BuildOverviewsDataInput) -> None:
    """Build map overviews for the steps the data group changed, and write them into their slots.

    Reads the repo's data group (``/data``, or ``/references`` when not materialized), only the
    steps the overviews lack or hold from an older write, and averages blocks of
    ``overview_factors`` pixels on the data's own grid into ``/overviews/<factor>``. The tile
    server uses the data group as full resolution and the overviews as coarser levels, and
    reprojects each tile on request. Units of whole shards run in this run, or fan out as child runs
    (``max_child_runs``).

    Parameters
    ----------
    args : BuildOverviewsDataInput
        Pydantic model containing all flow parameters. See BuildOverviewsDataInput for field descriptions.
    """
    overviews.build_overviews(args, runner=runner(args, CHILD_DEPLOYMENT))
