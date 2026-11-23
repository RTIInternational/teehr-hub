"""Run a project's evaluations (default: every one in ``platform``) through the control plane.

Each evaluation's latest version is started with ``POST .../evaluations/{slug}/runs`` and
waited on, one at a time (a run spreads across several pods on its own node group). Runs are
incremental: only the months whose inputs changed since the version's last run are
recomputed, so a run with nothing new is quick.

The control plane runs every job as its caller (ADR-0014). The flow calls it as the v1
flows' service account (:mod:`flows.auth`), a write member of ``platform``, so runs show
``service-account-teehr-platform-automation`` as their creator.
"""

import time
from typing import Any

from prefect import flow, get_run_logger, task

from flows.auth import control_plane, detail

#: Run statuses that are final.
DONE = ("succeeded", "failed", "cancelled")


@task(task_run_name="run {slug}")
def run_evaluation(
    project: str, slug: str, full: bool, poll_seconds: float, timeout_hours: float
) -> dict[str, Any]:
    """Start ``slug``'s latest version and wait for it; the run as the API returns it."""
    log = get_run_logger()
    with control_plane() as api:
        resp = api.post(
            f"/v1/projects/{project}/evaluations/{slug}/runs", json={"full": full}
        )
        if resp.status_code == 409:  # a run of this version is already going
            log.warning("%s: not started: %s", slug, detail(resp))
            return {"evaluation": slug, "status": "skipped", "error": detail(resp)}
        if resp.is_error:
            raise RuntimeError(f"{slug}: couldn't start a run ({resp.status_code}): "
                               f"{detail(resp)}")  # fmt: skip
        run = resp.json()
        log.info("%s v%s: run %s started", slug, run["version"], run["id"])
        deadline = time.monotonic() + timeout_hours * 3600
        while run["status"] not in DONE:
            if time.monotonic() > deadline:
                raise TimeoutError(f"{slug}: run {run['id']} still {run['status']} "
                                   f"after {timeout_hours}h")  # fmt: skip
            time.sleep(poll_seconds)
            got = api.get(f"/v1/projects/{project}/runs/{run['id']}")
            if got.is_error:  # a blip (e.g. a control-plane restart): try again
                log.warning("%s: reading run %s: %s", slug, run["id"], detail(got))
                continue
            run = got.json()
        log.info("%s: run %s %s: %s", slug, run["id"], run["status"],
                 run.get("result") or run.get("error"))  # fmt: skip
        return run


@flow(name="run-evaluations", log_prints=True)
def run_evaluations(
    project: str = "platform",
    evaluations: list[str] | None = None,
    full: bool = False,
    poll_seconds: float = 30,
    timeout_hours: float = 8,
) -> dict[str, str]:
    """Run ``evaluations`` (default: all of ``project``'s), one after another.

    ``full`` recomputes everything instead of only the changed months. Fails if any run
    didn't succeed (the rest still run). Returns each evaluation's run status.
    """
    log = get_run_logger()
    if evaluations is None:
        with control_plane() as api:
            resp = api.get(f"/v1/projects/{project}/evaluations")
            if resp.is_error:
                raise RuntimeError(f"listing {project}'s evaluations ({resp.status_code}): "
                                   f"{detail(resp)}")  # fmt: skip
            evaluations = sorted(e["slug"] for e in resp.json())
    log.info("running %d evaluation(s) in %s: %s", len(evaluations), project,
             ", ".join(evaluations))  # fmt: skip
    statuses: dict[str, str] = {}
    for slug in evaluations:
        try:
            run = run_evaluation(project, slug, full, poll_seconds, timeout_hours)
            statuses[slug] = run["status"]
        except Exception as exc:  # one evaluation's failure doesn't stop the rest
            log.error("%s: %s", slug, exc)
            statuses[slug] = "error"
    bad = {s: v for s, v in statuses.items() if v not in ("succeeded", "skipped")}
    if bad:
        raise RuntimeError(f"runs that didn't succeed: {bad}")
    return statuses
