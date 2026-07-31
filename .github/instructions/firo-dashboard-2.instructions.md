---
description: "Use when designing or implementing a FIRO dashboard feature in the API, frontend, or deployment workflow for this repo."
name: "FIRO Dashboard Guidance"
applyTo: ["api/src/**/firo*.py", "frontend/src/components/dashboards/firo/**", "frontend/src/context/FIRODashboard*.{js,jsx}", "examples/FIRO/**"]
---

# FIRO Dashboard Development Guidelines

Use these instructions when adding or changing the FIRO dashboard experience, its data flow, or the supporting deployment setup.

## General guidance

### General principles
- Start simple.
- Prefer small, reversible changes that fit the existing FastAPI + React architecture.
- Reuse existing patterns from the retrospective and forecast dashboards before introducing new abstractions.
- Keep the dashboard usable for local development with the existing MinIO and test data workflow.
- When a change affects both backend and frontend, update the API contract and the UI together.
- Document non-obvious decisions in code comments or nearby docs, especially around data assumptions and filters.

### Constraints
- **Do not modify** `MapComponent.jsx`, existing contexts, or existing dashboard components
- Only append to `api.js`; never change existing functions
- Start simple — no features beyond dataset/variable/timestep selection, tile display, and click popup
- No new npm dependencies without asking
- Plain JSX/JS; no TypeScript
- Match import order, naming, and `useCallback`/`useEffect` patterns from `dashboards/forecast/`

### Data and domain expectations
- Understand the data model before implementing the UI. In this repo, the dashboard typically relies on location, timeseries, and metric data flowing through the API.
- Treat FIRO-specific data as a variation of the existing dashboard patterns rather than a completely separate stack.
- If the dashboard depends on forecast or reservoir operations concepts, make the labels and filters understandable to non-experts and document any assumptions in the UI or code.
- Prefer server-side filtering and aggregation when possible to keep the frontend lightweight.

### Development workflow
- Before implementing, inspect the relevant existing dashboard and API routes to avoid duplicating logic.
- Keep changes scoped and testable. If a feature needs new data endpoints, add the endpoint and a simple client-side integration path together.
- When changing dependencies, update the relevant package or Python dependency files and consider local container rebuilds if needed.
- Verify the change with the relevant local workflow, such as the API, frontend build, or a targeted manual check in the local environment.
- When in doubt, favor the simplest implementation that can be explained clearly and extended later.

## Repository boundaries and submodule guidance

- Treat [teehr-cloud-core](teehr-cloud-core) as shared backend infrastructure, not as the main place for FIRO-specific dashboard implementation.
- Prefer keeping FIRO dashboard work isolated to this repository whenever possible.
- Do not modify the submodule unless a shared backend capability is genuinely required and cannot be achieved with existing endpoints, queryables, or frontend-side adaptation.
- When implementing dashboard features, first try to use existing API contracts and data shapes from the shared core service.
- If a backend change is truly necessary and it is reusable across projects, keep that change scoped and isolated in a dedicated submodule branch.
- If the change is dashboard-specific and not broadly reusable, prefer implementing it in this repository and avoid touching the submodule.
- Keep any submodule change minimal, well-documented, and clearly separated from UI and deployment work in this repo.

# Updates to initial implementation

