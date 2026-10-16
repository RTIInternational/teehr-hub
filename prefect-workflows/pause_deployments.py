"""Pause every deployment, e.g. on a staging cluster that shouldn't run schedules.

Run by the deployer job after `prefect deploy --all` when the deploy target sets
prefect.schedulesActive to false. Re-run after each deploy, since deploying
re-applies the schedules from prefect-remote.yaml. Pausing also deletes runs the
scheduler has already queued.
"""

import asyncio

from prefect import get_client


async def pause_all_deployments():
    async with get_client() as client:
        deployments = await client.read_deployments()
        for deployment in deployments:
            await client.pause_deployment(deployment.id)
            print(f"Paused deployment '{deployment.name}'")
        print(f"Paused {len(deployments)} deployment(s)")


if __name__ == "__main__":
    asyncio.run(pause_all_deployments())
