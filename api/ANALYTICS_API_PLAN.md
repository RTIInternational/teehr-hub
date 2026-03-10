# Plan: Async Spark-powered analytics web API (teehr-hub)

## Implementation Status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0 - Reconnaissance | ✅ Complete | Chose `custom_metrics` analytics |
| Phase 1 - API Contracts | ✅ Complete | `api/src/models/analytics.py`, `api/src/routes/analytics.py` |
| Phase 2 - Run Tracking | ✅ Complete | DDL in `warehouse/01_initialization/create_analytics_runs.sql` |
| Phase 3 - K8s Job Submission | ✅ Complete | `api/src/k8s/jobs.py`, RBAC in `api/manifests/api-rbac.yaml` |
| Phase 4 - Analytics Driver | ✅ Complete | `spark-analytics-driver/` package |
| Phase 5 - Status + Results | ✅ Complete | Wired in routes |
| Phase 6 - Caching | ✅ Complete | Implemented in POST endpoint |
| Phase 7 - Hardening | 🔲 Pending | TTL, concurrency limits, observability |

### Quick Start (after deployment)
1. Create the results schema: `CREATE SCHEMA IF NOT EXISTS iceberg.teehr_results`
2. Create tracking table: Run `warehouse/01_initialization/create_analytics_runs.sql`
3. Deploy API with new manifests (includes RBAC)
4. Build/push analytics driver image from `spark-analytics-driver/`

---

## Goal
Expose selected Spark analytics (minutes-scale) as an **async web API**:
- Client submits an analytics request (with richer user inputs than simple filters)
- API returns a `run_id` immediately
- Spark job runs on Kubernetes, reads Iceberg (S3), writes a derived Iceberg result table (separate schema/namespace)
- Client polls for status and fetches results via API (served from Trino querying the result table)

This plan fits existing teehr-hub patterns:
- FastAPI in `api/src/*`
- Trino querying utilities in `api/src/database.py`
- Spark-on-k8s driver patterns in `prefect-workflows/workflows/utils/common_utils.py` using `teehr.evaluation.spark_session_utils.create_spark_session`
- Existing service account patterns for Spark executors (e.g., `prefect-job`)

---

## Architecture decisions (make these explicit up front)
1) Job runner choice:
   - **A1 (recommended): FastAPI creates Kubernetes Jobs** that run a Spark driver container.
   - A2: FastAPI triggers Prefect flow runs (Prefect as job submission/status system).

This plan assumes **A1 (FastAPI -> Kubernetes Job)**.

2) Result storage:
   - Materialize results as Iceberg tables in a separate namespace, e.g.:
     - Trino/Spark catalog: `iceberg`
     - Source schema: `teehr`
     - Result schema: `teehr_results` (or `teehr_api_results`)

3) Caching:
   - Cache key = hash of `{analytics_id, analytics_version, normalized_parameters, (optional) input data boundary}`
   - If a completed result for same cache key exists and is “fresh enough”, skip job submission and return existing `run_id` / `result_table`.

---

## Phase 0 — repo reconnaissance (1–2 hours)
- Locate:
  - existing FastAPI routes in `api/src/routes/*` (router included in `api/src/routes/__init__.py`)
  - Trino access in `api/src/database.py`
  - Spark session utilities used by Prefect: `prefect-workflows/workflows/utils/common_utils.py`
- Decide the first analytics to expose (start with 1).

Deliverable: choose `analytics_id = "example_analytics"` and define its input schema.

---

## Phase 1 — Define data model + API contracts (no k8s yet)
### 1. Add Pydantic models for runs
Create:
- `api/src/models/analytics.py` with:
  - `AnalyticsRunCreateRequest`
  - `AnalyticsRunCreateResponse`
  - `AnalyticsRunStatusResponse`
  - `AnalyticsResultResponse` (optional; could just return rows)

Fields to include:
- `run_id: str` (UUID)
- `analytics_id: str`
- `parameters: dict`
- `cache_key: str`
- `status: Literal["queued","running","succeeded","failed"]`
- `created_at`, `started_at`, `finished_at`
- `result_catalog`, `result_schema`, `result_table`
- `error_message` (nullable)

### 2. Add new FastAPI router
Create:
- `api/src/routes/analytics.py`

Endpoints:
- `POST /analytics/{analytics_id}/runs`
- `GET  /analytics/runs/{run_id}`
- `GET  /analytics/runs/{run_id}/results?limit=&offset=` (or page cursor)

Update:
- `api/src/routes/__init__.py` to include the new router.

Deliverable: endpoints return stub responses (no job submission yet).

---

## Phase 2 — Add persistent run tracking (minimal viable)
### Option 2A (simple): store run metadata in an Iceberg table
Create a small Iceberg table `iceberg.teehr_results.analytics_runs` with columns:
- run_id (string)
- analytics_id (string)
- cache_key (string)
- status (string)
- parameters_json (string)
- result_table (string)
- created_at (timestamp)
- started_at (timestamp)
- finished_at (timestamp)
- error_message (string)

Implementation:
- Use existing Trino `execute_query()` for INSERT/UPDATE (or create helper that issues `INSERT INTO` / `UPDATE` if supported).
- Alternative if Trino UPDATE is painful: store only immutable events (append-only) and compute latest state by query.

Deliverable:
- `POST` inserts a row status=queued
- `GET status` reads from table

NOTE: If you prefer Postgres, you already have `prefect-pg`, but that DB is “Prefect’s DB”. Consider a dedicated API DB if going that route.

---

## Phase 3 — Implement Kubernetes Job submission from FastAPI
### 1) Add k8s client dependency + config
- Add Python dependency: `kubernetes`
- Add configuration:
  - `API_JOB_NAMESPACE` (default `teehr-hub`)
  - `API_JOB_IMAGE` (spark driver image to run analytics)
  - `API_JOB_SERVICE_ACCOUNT` (e.g., `prefect-job` or a new `api-job` SA)
  - resource requests/limits

Create:
- `api/src/k8s/jobs.py` with:
  - `create_analytics_job(run_id, analytics_id, parameters, env, image, namespace, service_account)`
  - `get_job_status(run_id)` (or by job name)
  - `get_job_logs_link(...)` (optional)

Job naming:
- `teehr-analytics-{run_id[:8]}`

Job env vars passed into pod:
- `RUN_ID`
- `ANALYTICS_ID`
- `PARAMETERS_JSON`
- Iceberg/S3 config env vars (same as Prefect jobs use)
- any auth/IRSA assumptions (service account annotation)

Deliverable: `POST` creates a Kubernetes Job and returns `run_id`.

### 2) RBAC
Add manifests:
- `api/manifests/api-job-sa.yaml` (ServiceAccount)
- `api/manifests/api-job-rbac.yaml` (Role/RoleBinding) granting FastAPI pod permission to:
  - create/get/list/watch Jobs in namespace
  - optionally get pods/logs for status & debugging

Also ensure the analytics driver job’s service account has:
- permission to spawn Spark executors (Spark RBAC already exists for `prefect-job`)
- S3 write access to results namespace (IRSA role)

Deliverable: FastAPI can submit jobs in-cluster.

---

## Phase 4 — Build the “analytics driver” entrypoint (Spark job code)
### 1) Create a dedicated driver package/script
Create new directory (choose one):
- `spark-analytics-driver/` (new image)
OR reuse prefect image and add a module under:
- `prefect-workflows/workflows/on_demand/`

Recommended structure (new python module):
- `spark_analytics_driver/__main__.py`
- `spark_analytics_driver/analytics_registry.py`
- `spark_analytics_driver/analytics/example_analytics.py`

Responsibilities:
- Parse env vars (`RUN_ID`, `ANALYTICS_ID`, `PARAMETERS_JSON`)
- Create spark session using `teehr.evaluation.spark_session_utils.create_spark_session`
  - ensure executor SA is correct (same as Prefect pattern)
- Run analytics function from registry
- Materialize results to Iceberg:
  - result schema = `teehr_results`
  - result table name = `analytics_{analytics_id}_{cache_key_prefix}` OR `run_{run_id}`
- Update `analytics_runs` table status to succeeded/failed + result table name + timestamps

Deliverable: running driver locally (or in-cluster) produces an Iceberg table result.

### 2) Container image
Add Dockerfile (example):
- `spark-analytics-driver/Dockerfile`
Base it off your Prefect image OR use a slimmer python+java base.
Must include:
- Java
- pyspark deps as needed
- `teehr` library version matching environment

Deliverable: image published to ECR (or whatever you use), referenced by `API_JOB_IMAGE`.

---

## Phase 5 — Wire status updates + results retrieval
### 1) Status endpoint behavior
`GET /analytics/runs/{run_id}` should:
- first check k8s Job status (pending/running/succeeded/failed)
- reflect that into `analytics_runs` table if out-of-date
- return status payload

### 2) Results endpoint behavior
`GET /analytics/runs/{run_id}/results` should:
- read `result_table` from `analytics_runs`
- query Trino: `SELECT * FROM iceberg.teehr_results.{result_table} LIMIT/OFFSET`
- return JSON rows (or OGC-ish if needed)

Deliverable: end-to-end: submit -> job runs -> poll -> fetch results.

---

## Phase 6 — Add caching
In `POST /analytics/{analytics_id}/runs`:
- compute `cache_key = sha256(normalized_parameters + analytics_version + analytics_id)`
- query `analytics_runs` for a succeeded run with same cache_key (and optional TTL rules)
- if found: return that run_id + status=succeeded + result_table
- else: create new run + submit job

Deliverable: repeat submissions reuse result.

---

## Phase 7 — Operational hardening
- Timeouts:
  - Job activeDeadlineSeconds (e.g., 20 minutes)
- Concurrency:
  - limit per-user or global (simple semaphore in API, or use k8s quotas)
- Cleanup:
  - TTL policy for old result tables (Iceberg expire snapshots + drop old tables)
- Observability:
  - include job_name in API response
  - link to logs (Grafana/Loki, kubectl logs, etc.)

---

## Acceptance criteria (definition of done)
- Can submit `POST /analytics/{analytics_id}/runs` and receive run_id immediately
- A Kubernetes Job starts and runs Spark analytics successfully
- Results appear as an Iceberg table in `iceberg.teehr_results`
- API status endpoint transitions: queued -> running -> succeeded/failed
- API results endpoint returns paginated rows from the result table via Trino
- Caching works for identical inputs

---

## Notes / repo references
FastAPI app/router:
- `api/src/main.py`
- `api/src/routes/__init__.py`

Trino utilities:
- `api/src/database.py`

Spark session pattern used by Prefect:
- `prefect-workflows/workflows/utils/common_utils.py` uses `create_spark_session()` and ensures executor SA.

Kubernetes + Prefect patterns (helpful reference):
- `prefect-workflows/prefect-remote.yaml` (env vars and service account usage)
