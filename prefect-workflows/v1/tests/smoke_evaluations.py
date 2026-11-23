"""Smoke test: the run-evaluations flow against a fake control plane, in the v1 image.

    docker run --rm -v "$PWD/prefect-workflows/v1:/teehr-v1:ro" teehr-prefect-v1:test \
        python /teehr-v1/tests/smoke_evaluations.py
"""

import json

import httpx

import flows.evaluations as ev

polls: dict[str, int] = {}
started: list[dict] = []


tokens: list[str] = []
calls: list[str] = []


def handle(request: httpx.Request) -> httpx.Response:
    assert request.headers["Authorization"] == f"Bearer {tokens[-1]}"
    calls.append(request.url.path)
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


def keycloak(request: httpx.Request) -> httpx.Response:
    form = dict(httpx.QueryParams(request.content.decode()))
    if form != {"grant_type": "client_credentials", "client_id": "bot",
                "client_secret": "s3cret"}:
        return httpx.Response(401, json={"error": "unauthorized_client"})
    tokens.append(f"t{len(tokens)}")
    # 60 s: within the renewal minute at once, so every request gets a new token.
    return httpx.Response(200, json={"access_token": tokens[-1], "expires_in": 60})


ev.httpx.post = lambda url, data, timeout: keycloak(httpx.Request("POST", url, data=data))
ev.os.environ.update(POLARIS_OAUTH2_SERVER_URI="http://kc/token", POLARIS_CLIENT_ID="bot",
                     POLARIS_CLIENT_SECRET="s3cret")
real = ev._client
ev._client = lambda: httpx.Client(
    base_url="http://cp", auth=real().auth, transport=httpx.MockTransport(handle)
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

assert len(tokens) == len(calls)  # renewed before each request

try:
    ev.ClientCredentials("http://kc/token", "bot", "wrong")._fresh()
    raise AssertionError("a refused secret should fail")
except RuntimeError as exc:
    assert "token for bot (401)" in str(exc), exc
# Deployed, the secret comes from the Prefect Secret block, not the environment.
from prefect.blocks.system import Secret  # noqa: E402

from flows.catalog import SECRET_BLOCK, client_secret  # noqa: E402

del ev.os.environ["POLARIS_CLIENT_SECRET"]
Secret(value="from-block").save(name=SECRET_BLOCK, overwrite=True)
assert client_secret() == "from-block"
print("OK")
