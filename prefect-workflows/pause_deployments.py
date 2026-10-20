"""Pause (or with --resume, resume) every deployment.

Run by the deployer job after `prefect deploy --all` when the deploy target sets
prefect.schedulesActive to false, e.g. a staging cluster. Re-run after each
deploy, since deploying re-applies the schedules from prefect-remote.yaml.
Pausing also deletes runs the scheduler has already queued.

Also usable by hand against a running cluster (the worker image has Prefect and
PREFECT_API_URL):

    kubectl exec -i deploy/prefect-worker -- python - < pause_deployments.py
    kubectl exec -i deploy/prefect-worker -- python - --resume < pause_deployments.py
"""

import asyncio
import sys

from prefect import get_client


async def set_all_deployments(paused: bool):
    async with get_client() as client:
        deployments = await client.read_deployments()
        for deployment in deployments:
            if paused:
                await client.pause_deployment(deployment.id)
            else:
                await client.resume_deployment(deployment.id)
        verb = "Paused" if paused else "Resumed"
        print(f"{verb} {len(deployments)} deployment(s)")


if __name__ == "__main__":
    asyncio.run(set_all_deployments(paused="--resume" not in sys.argv[1:]))
