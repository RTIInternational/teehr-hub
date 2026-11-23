"""The v1 flows' identity: the ``teehr-platform-automation`` service account, a write member
of the system projects (ADR-0020 in teehr-cloud-core).

Every v1 flow acts as it, whether it writes tables through the catalog
(:func:`flows.catalog.catalog`) or calls the control plane's API (:func:`control_plane`).
Its client id and Keycloak's token endpoint come from the work pool's environment; its
secret from a Prefect Secret block (loaded by load-secrets), so it isn't in the
deployments' job variables.
"""

import os
import time

import httpx

#: The Prefect Secret block holding the client's secret.
SECRET_BLOCK = "teehr-platform-automation-secret"


def client_id() -> str:
    return os.environ["POLARIS_CLIENT_ID"]


def token_url() -> str:
    """Keycloak's token endpoint (in-cluster; tokens still carry the public issuer)."""
    return os.environ["POLARIS_OAUTH2_SERVER_URI"]


def client_secret() -> str:
    """``POLARIS_CLIENT_SECRET`` if set (local tests), else the Prefect Secret block."""
    if os.environ.get("POLARIS_CLIENT_SECRET"):
        return os.environ["POLARIS_CLIENT_SECRET"]
    from prefect.blocks.system import Secret

    return Secret.load(SECRET_BLOCK).get()


def detail(resp: httpx.Response) -> str:
    """An error response's message (the API's ``detail``, else the body)."""
    try:
        return str(resp.json().get("detail") or resp.text)
    except ValueError:
        return resp.text


class ClientCredentials(httpx.Auth):
    """Bearer tokens for the client from Keycloak, renewed a minute before they expire
    (a flow may run for hours; tokens last minutes)."""

    def __init__(self, token_url: str, client_id: str, client_secret: str):
        self._form = {"grant_type": "client_credentials", "client_id": client_id,
                      "client_secret": client_secret}  # fmt: skip
        self._token_url = token_url
        self._token, self._expires = "", 0.0

    def _fresh(self) -> str:
        if time.monotonic() > self._expires - 60:
            resp = httpx.post(self._token_url, data=self._form, timeout=30)
            if resp.is_error:
                raise RuntimeError(f"getting a token for {self._form['client_id']} "
                                   f"({resp.status_code}): {detail(resp)}")  # fmt: skip
            body = resp.json()
            self._token = body["access_token"]
            self._expires = time.monotonic() + float(body.get("expires_in", 300))
        return self._token

    def auth_flow(self, request: httpx.Request):
        request.headers["Authorization"] = f"Bearer {self._fresh()}"
        yield request


def control_plane(timeout: float = 60) -> httpx.Client:
    """An HTTP client for the control plane's API (``CONTROL_PLANE_URL``, default the
    in-cluster service), as the service account."""
    return httpx.Client(
        base_url=os.environ.get("CONTROL_PLANE_URL", "http://teehr-control-plane:8000"),
        auth=ClientCredentials(token_url(), client_id(), client_secret()),
        timeout=timeout,
    )
