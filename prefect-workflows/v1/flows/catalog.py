"""The v1 warehouse's catalog (Polaris) for v1 flows, as the flows' service account.

The flows act as ``teehr-platform-automation`` (OAuth2 client credentials), a write
member of the system projects (ADR-0020 in teehr-cloud-core). Polaris vends storage
credentials per table.
"""

import os
from typing import Any

from pyiceberg.catalog import Catalog, load_catalog

#: The Prefect Secret block holding the client's secret (loaded by load-secrets).
SECRET_BLOCK = "teehr-platform-automation-secret"


def client_secret() -> str:
    """The flows' client secret: ``POLARIS_CLIENT_SECRET`` if set (local tests), else the
    Prefect Secret block, so the secret isn't in the deployments' job variables."""
    if os.environ.get("POLARIS_CLIENT_SECRET"):
        return os.environ["POLARIS_CLIENT_SECRET"]
    from prefect.blocks.system import Secret

    return Secret.load(SECRET_BLOCK).get()


def catalog() -> Catalog:
    """The Polaris REST catalog, configured from the work pool's environment.

    Its OAuth2 auth gets a new access token before the last one expires (Keycloak's last
    five minutes), so a long flow's later calls, such as a build's commit, aren't refused.
    """
    realm = os.environ["POLARIS_DEFAULT_REALM"]
    properties: dict[str, Any] = {
        "type": "rest",
        "uri": os.environ["REMOTE_CATALOG_REST_URI"],
        "warehouse": os.environ.get("REMOTE_WAREHOUSE_IDENTIFIER") or realm,
        "auth": {
            "type": "oauth2",
            "oauth2": {
                "client_id": os.environ["POLARIS_CLIENT_ID"],
                "client_secret": client_secret(),
                "token_url": os.environ["POLARIS_OAUTH2_SERVER_URI"],
                "scope": "openid",
            },
        },
        "header.X-Polaris-Realm": realm,
        "header.X-Iceberg-Access-Delegation": "vended-credentials",
        "s3.region": os.environ["AWS_REGION"],
    }
    endpoint = os.environ.get("REMOTE_CATALOG_S3_ENDPOINT")
    if endpoint:  # local object storage (KinD)
        properties["s3.endpoint"] = endpoint
    if os.environ.get("REMOTE_CATALOG_S3_PATH_STYLE_ACCESS", "").lower() == "true":
        properties["s3.path-style-access"] = "true"
    return load_catalog("polaris", **properties)
