"""Smoke test: the run-evaluations flow against a fake control plane, in the v1 image.

    docker run --rm -v "$PWD/prefect-workflows/v1:/teehr-v1:ro" teehr-prefect-v1:test \
        python /teehr-v1/tests/smoke_evaluations.py
"""

import json

import httpx

import flows.evaluations as ev

polls: dict[str, int] = {}
started: list[dict] = []


def handle(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == "Bearer tpat_test"
    path = request.url.path
    if path == "/v1/projects/platform/evaluations":
        return httpx.Response(200, json=[{"slug": s} for s in ("b_eval", "a_eval", "busy")])
    if path.endswith("/runs") and request.method == "POST":
        slug = path.split("/")[-2]
        if slug == "busy":
            return httpx.Response(409, json={"detail": "busy v1 already has a run going"})
        started.append({"slug": slug, **json.loads(request.content)})
        return httpx.Response(202, json={"id": f"run-{slug}", "version": 1, "status": "queued"})
    if "/runs/" in path:
        run_id = path.rsplit("/", 1)[-1]
        polls[run_id] = polls.get(run_id, 0) + 1
        if polls[run_id] == 1:
            return httpx.Response(503, json={"detail": "restarting"})  # a blip
        status = "running" if polls[run_id] < 3 else (
            "failed" if run_id == "run-b_eval" else "succeeded")
        return httpx.Response(200, json={"id": run_id, "version": 1, "status": status,
                                         "result": {"rows": 10}, "error": None})
    return httpx.Response(404)


ev.os.environ["CONTROL_PLANE_TOKEN"] = "tpat_test"
real = ev._client
ev._client = lambda: httpx.Client(
    base_url="http://cp", headers=real().headers, transport=httpx.MockTransport(handle)
)

try:
    ev.run_evaluations(poll_seconds=0)
    raise AssertionError("a failed run should fail the flow")
except RuntimeError as exc:
    assert "b_eval" in str(exc) and "a_eval" not in str(exc), exc
assert [s["slug"] for s in started] == ["a_eval", "b_eval"], started  # sorted, busy skipped
assert all(s["full"] is False for s in started)

started.clear()
polls.clear()
out = ev.run_evaluations(evaluations=["a_eval"], full=True, poll_seconds=0)
assert out == {"a_eval": "succeeded"} and started == [{"slug": "a_eval", "full": True}]

ev.os.environ["CONTROL_PLANE_TOKEN"] = "{{ $CONTROL_PLANE_TOKEN }}"  # secret missing
try:
    real()
    raise AssertionError("a missing token should be refused")
except RuntimeError as exc:
    assert "prefect-control-plane-token" in str(exc)
print("OK")
