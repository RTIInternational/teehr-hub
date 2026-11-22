from prefect import flow
from teehr_icechunk import overviews

from workflows.models.ingest_gridded_data_input import BuildOverviewsDataInput


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
    reprojects each tile on request.

    Parameters
    ----------
    args : BuildOverviewsDataInput
        Pydantic model containing all flow parameters. See BuildOverviewsDataInput for field descriptions.
    """
    overviews.build_overviews(args)
