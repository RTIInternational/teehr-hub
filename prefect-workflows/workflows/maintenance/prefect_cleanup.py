import asyncio
from datetime import datetime, timedelta, timezone
from prefect import flow, get_run_logger, get_client
from prefect.client.schemas import StateType
from prefect.server.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterState,
    FlowRunFilterStateType,
    # FlowRunFilterStateName,
    FlowRunFilterStartTime,
)


@flow(name="Cleanup Old Flow Runs")
async def rm_completed_flow_runs(age_limit_days: int = 14):
    """Retrieve prefect flow runs older than 14 days and delete them."""
    logger = get_run_logger()

    lookback_dt = datetime.now(timezone.utc) - timedelta(days=age_limit_days)
    # lookback_dt = datetime.now(timezone.utc) - timedelta(minutes=20)

    logger.info(f"Deleting flow runs older than {lookback_dt}.")

    async with get_client() as client:
        rm_runs = []
        read_ct = 999
        while read_ct > 0:
            flow_runs = await client.read_flow_runs(
                flow_run_filter=FlowRunFilter(
                    start_time=FlowRunFilterStartTime(before_=lookback_dt),
                    state=FlowRunFilterState(
                        type=FlowRunFilterStateType(any_=[StateType.COMPLETED])
                    ),
                ),
                offset=len(rm_runs),
            )
            read_ct = len(flow_runs)
            if read_ct == 200:
                logger.info(
                    "Retrieved the limit of 200 flow runs. There are likely more. Checking..."
                )
            rm_runs.extend(flow_runs)

        logger.info(
            f"Found {len(rm_runs)} flow runs to delete (Status=COMPLETED, Start Time < {lookback_dt})."
        )

        for flow_run in rm_runs:
            logger.debug(
                f"Deleting flow run {flow_run.id} with state {flow_run.state}."
            )
            await client.delete_flow_run(flow_run_id=flow_run.id)

        investigate_flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                start_time=FlowRunFilterStartTime(before_=lookback_dt),
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(not_any_=[StateType.COMPLETED])
                ),
            )
        )
        logger.info(
            f"Note: There are {len(investigate_flow_runs)} flow runs that require manual resolution (status!=COMPLETED)."
        )


if __name__ == "__main__":
    asyncio.run(rm_completed_flow_runs(age_limit_days=2))
