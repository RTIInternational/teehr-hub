# TEEHR Access Control Matrix

This document summarizes how access is currently enforced across services in this repository.

Last updated: 2026-05-15

## Identity Model

Keycloak uses both groups and roles:

- Groups are assigned to users.
- Groups can grant realm roles and client roles.
- Some services authorize by role claims.
- Some services authorize by group claims.

## Group to Role Mapping (Current Bootstrap)

Source: [keycloak-bootstrap/manifests/realm-configmap.yaml.tpl](../keycloak-bootstrap/manifests/realm-configmap.yaml.tpl#L31)

| Group | Realm role(s) granted | Extra client roles |
|---|---|---|
| basic-user | basic-user | None |
| iceberg-user | iceberg-user | None |
| jupyter-user | jupyter-user | None |
| jupyter-admin | jupyter-user | None |
| key-management-admin | admin | None |
| prefect-admin | admin | None |
| webapi-admin | admin | realm-management: manage-users, query-users, view-users, query-groups, view-realm |

## Service Access Matrix

| Service | Enforcement point | Uses groups or roles | Who can access today |
|---|---|---|---|
| TEEHR dashboards (Retrospective, Forecast, Data page) | Frontend authenticated-route guard | Authenticated state only | Any logged-in user |
| TEEHR admin UI | Frontend admin-route guard | Role: admin | Users in key-management-admin, prefect-admin, or webapi-admin (all map to admin) |
| API key management endpoints | API admin identity dependency | Role: admin | Users in key-management-admin, prefect-admin, or webapi-admin (all map to admin) |
| Prefect UI | Prefect oauth2-proxy allowed-group | Group: prefect-admin | Users in prefect-admin |
| JupyterHub login | GenericOAuthenticator allowed_groups | Groups: jupyter-user, jupyter-admin | Users in jupyter-user or jupyter-admin |
| JupyterHub admin privileges | JupyterHub Authenticator admin_groups | Group: jupyter-admin | Users in jupyter-admin |
| Keycloak admin console link in TEEHR admin page | TEEHR frontend admin visibility | Role: admin | Users with admin role (same as TEEHR admin UI) |
| Keycloak admin console capabilities | Keycloak permissions | Role and client roles | Intended primary group appears to be webapi-admin due to realm-management client roles |
| Iceberg or Trino end-user auth | Not fully wired in this repo | No clear active user-facing Keycloak gate | Undetermined from current implementation |

## Important Notes

1. key-management-admin and prefect-admin both grant the admin realm role, so both can administer API keys in the current API and frontend implementation.
2. Prefect is intentionally stricter: it checks membership in the prefect-admin group directly, not just the admin role.
3. JupyterHub authorization is also group-based, not based on the admin realm role.
4. Iceberg REST auth rollout is deferred per plan and appears not fully enforced for end-user role mapping yet.

## Code and Config References

- Frontend authenticated-route guard: [frontend/src/App.jsx](../frontend/src/App.jsx#L16)
- Frontend admin-role check: [frontend/src/App.jsx](../frontend/src/App.jsx#L56)
- Frontend navbar admin visibility: [frontend/src/components/common/Navbar.jsx](../frontend/src/components/common/Navbar.jsx#L8)
- API admin identity dependency: [api/src/auth.py](../api/src/auth.py#L183)
- API key routes using admin identity: [api/src/routes/auth.py](../api/src/routes/auth.py#L25)
- Prefect group gate: [prefect-server/manifests/oauth2-proxy.yaml.tpl](../prefect-server/manifests/oauth2-proxy.yaml.tpl#L165)
- Prefect groups claim source: [prefect-server/manifests/oauth2-proxy.yaml.tpl](../prefect-server/manifests/oauth2-proxy.yaml.tpl#L166)
- JupyterHub allowed groups: [jupyterhub/garden.yaml](../jupyterhub/garden.yaml#L57)
- JupyterHub admin groups: [jupyterhub/garden.yaml](../jupyterhub/garden.yaml#L68)
- Iceberg REST auth status in plan: [plan.md](../plan.md#L46)
