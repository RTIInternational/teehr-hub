# TEEHR Hub Authentication Plan

Last updated: 2026-05-08

## Guardrails
- Development target is local kind only.
- Cluster changes are applied through Garden + manifests only.
- Do not run commands against remote environments/clusters.

## Decisions
- Auth service: Keycloak with Official Keycloak Operator.
- Priority 1 integrations: FastAPI + React frontend.
- JupyterHub will migrate from GitHub OAuth to Keycloak OIDC.
- API keys: app-managed opaque keys in PostgreSQL.
- Signup: self-service with limited default permissions and stricter anonymous limits.
- Account lifecycle: self-service signup with automatic baseline access (basic-user) and admin-managed elevated access.
- Password reset: support self-service reset via Keycloak email flow (SMTP-backed).

## Phase 1: Keycloak Infrastructure
1. [x] Deploy keycloak-pg module (PostgreSQL) with two databases:
   - keycloak
   - teehr_api
2. [x] Deploy keycloak-operator module (Official Keycloak Operator via OLM subscription manifests).
3. [x] Deploy keycloak module (Keycloak CR managed by operator).
4. [x] Add secrets in local and remote secret varfiles for future environment parity.

## Phase 2: FastAPI Authentication (Priority 1)
1. [x] Add JWT validation against Keycloak JWKS.
2. [x] Add anonymous vs authenticated rate limiting.
3. [x] Add API key CRUD and validation endpoints.
4. [x] Restrict API key management routes to admin JWT identities.
5. [x] Add Swagger/OpenAPI auth schemes (Bearer, API Key, OAuth2 Keycloak).
6. [x] Move API key DB connection config to Kubernetes secrets.

## Phase 3: Frontend Authentication (Priority 1)
1. [x] Integrate Keycloak JS adapter.
2. [x] Wire login/logout/user profile.
3. [x] Attach bearer token to API requests.
4. [x] Add admin-only API key management page (list/create/revoke).
5. [x] Fix auth header merge bug that dropped Authorization on requests with custom headers.

## Phase 4: JupyterHub OIDC Migration (Priority 2)
1. [x] Replace GitHub auth with Keycloak OIDC.
2. [x] Map Keycloak groups to JupyterHub permissions.

## Phase 5: Iceberg REST Authentication (Priority 2)
1. [-] Add auth proxy in front of Iceberg REST.
2. [ ] Add service account flow for Trino-to-Iceberg calls.

## Phase 6: Prefect + Grafana (Priority 3)
1. [ ] Keep hardcoded admin fallback if needed.
2. [ ] Prefer OIDC integration where feasible.

## Phase 7: Account Lifecycle (Priority 2)
1. [ ] Signup + approval workflow:
   - Keep self-registration enabled.
   - New users are auto-assigned to baseline access group: basic-user.
   - Admin grants elevated access by adding users to additional groups (for example: jupyter-user, admin).
2. [ ] Password reset workflow:
   - Enable "Forgot Password" in Keycloak login.
   - Configure SMTP using Kubernetes secrets.
   - Require email verification before reset where applicable.
3. [ ] API/Frontend access policy:
   - Ensure app authorization checks require approved roles for protected features.
   - Keep admin-only management routes restricted to admin JWT identities.

## Legend
- [x] Done
- [-] In progress / partially implemented
- [ ] Pending
