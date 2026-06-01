# Iceberg Auth and Storage Permissions Roadmap

Last updated: 2026-05-10
Status: deferred for active implementation

## Why this document exists

This document captures a future implementation plan for Iceberg security so we can pause active changes now and resume later with a clear path.

## Problem framing

Iceberg protection has two distinct layers:

1. API/catalog access control:
- Who can call the Iceberg REST catalog endpoints.

2. Object storage access control:
- Who can read/write/delete underlying metadata, manifests, and data files.

If only API auth is implemented and storage credentials are broad, data is still effectively over-exposed.

## Current state

1. Catalog service:
- `iceberg-rest` is deployed.
- A non-breaking `iceberg-rest-auth` proxy exists in-cluster and can enforce auth via `teehr-api /auth/me`.
- Existing consumers still target `iceberg-rest` by default.

2. Storage identity:
- `iceberg-rest` uses a service account IAM role for S3 access.
- Access model is service-level, not user-level.

3. Consumer flows:
- Trino, JupyterHub, and Prefect workflows consume `${var.iceberg.catalogUri}`.

## Standard implementation patterns

### Pattern A: shared service identity (coarse)

1. One role for all catalog/engine access to storage.
2. Fastest to operate.
3. Weak least-privilege and attribution.

### Pattern B: catalog authz plus shared storage identity (middle)

1. Stronger API-level authz at catalog/proxy.
2. Storage still uses backend service role.
3. Good near-term balance of security and complexity.

### Pattern C: credential vending (fine-grained)

1. OIDC-authenticated subject obtains short-lived scoped cloud credentials.
2. Per-user/per-workload storage attribution and least-privilege.
3. Most complex to implement and operate.

## Recommended target path for this repo

Use Pattern B first, then evaluate Pattern C when needed.

### Phase 5A: stabilize API guard (short term)

1. Keep `iceberg-rest-auth` proxy as the front-door for catalog API access.
2. Enforce auth for all external/in-cluster consumer paths that should be protected.
3. Keep direct `iceberg-rest` service only for controlled migration/testing windows.

### Phase 5B: consumer migration (short term)

1. Switch catalog URI consumers from `http://iceberg-rest:8181` to `http://iceberg-rest-auth:8181`:
- Trino
- JupyterHub runtime env
- Prefect workflows
2. Validate read and write workflows before removing direct path usage.

### Phase 5C: storage least-privilege baseline (medium term)

1. Split IAM roles by capability:
- read-only role
- writer role
- maintenance/admin role
2. Scope policies to explicit bucket prefixes per environment.
3. Deny destructive operations to read-only paths.
4. Confirm KMS permissions match data access boundaries.

### Phase 5D: advanced model (future)

1. Evaluate credential vending for per-user/per-job temporary credentials.
2. Add subject-level audit mapping from identity to storage actions.

## Practical guardrails

1. No long-lived static storage keys in committed files.
2. Use service-account roles and short-lived credentials where possible.
3. Separate dev/stage/prod storage boundaries.
4. Prefer explicit allow lists and deny-by-default policies.
5. Keep destructive maintenance operations separate from normal query roles.

## Security checks before marking complete

1. Unauthenticated request to catalog front-door fails.
2. Authenticated request with baseline role succeeds for allowed reads.
3. Unauthorized writes/deletes are blocked by policy.
4. Trino/Jupyter/Prefect all function through guarded endpoint.
5. Audit logs show who/what accessed catalog and storage.

## Deferred implementation decision

The team has intentionally paused active Iceberg auth/storage hardening after initial scaffolding.
Resume using this document as the implementation checklist.
