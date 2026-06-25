---
description: "Use when designing or implementing a FIRO dashboard feature in the API, frontend, or deployment workflow for this repo."
name: "FIRO Dashboard Guidance"
applyTo: ["api/src/**", "frontend/src/**", "panel-dashboards/**", "examples/FIRO/**"]
---

# FIRO Dashboard Development Guidelines

Use these instructions when adding or changing the FIRO dashboard experience, its data flow, or the supporting deployment setup.

## General principles
- Prefer small, reversible changes that fit the existing FastAPI + React architecture.
- Reuse existing patterns from the retrospective and forecast dashboards before introducing new abstractions.
- Keep the dashboard usable for local development with the existing MinIO and test data workflow.
- When a change affects both backend and frontend, update the API contract and the UI together.
- Document non-obvious decisions in code comments or nearby docs, especially around data assumptions and filters.

## Backend guidance
- Favor the existing API structure under api/src/routes and keep new endpoints consistent with the current OGC-style patterns.
- Reuse existing query helpers, database access utilities, and auth middleware rather than introducing new plumbing.
- When adding data access for FIRO features, make the query parameters explicit and filterable; avoid hard-coded table names unless the workflow is truly one-off.
- Preserve authentication expectations and rate limiting behavior unless the task explicitly requires relaxed access.
- If new backend dependencies are needed, confirm whether they are already available in the API image or Python environment. If not, update the relevant dependency declaration rather than relying on ad hoc installs.
- For local development, assume the data will be served from the existing warehouse setup and make endpoints robust to sparse or partially populated datasets.
- If a new endpoint is required, prefer a narrow resource-focused contract and return structured JSON that the frontend can consume directly.
- For deployment-related work, align new config and environment variables with the existing config pattern and avoid hard-coding hostnames or credentials.

## Frontend guidance
- Follow the current React layout and routing style in frontend/src and keep dashboard-specific code grouped under the relevant dashboard folder.
- Reuse existing dashboard context providers, hooks, and shared UI components before adding new state management layers.
- Preserve a clear separation between view components, data-loading hooks, and context state. Keep state shape predictable and serializable.
- For map-based UI work, keep filters and controls explicit and easy to reason about. If a map control changes the visible data, make the related state update in the shared dashboard context rather than in local component state only.
- For any new FIRO-specific route or page, add it to the app router in a way that matches the existing auth and layout conventions.
- Keep dashboard layout responsive and consistent with the existing Bootstrap-based styling.
- If new map components, charts, or controls are introduced, make them reusable and keep their props minimal.

## Data and domain expectations
- Understand the data model before implementing the UI. In this repo, the dashboard typically relies on location, timeseries, and metric data flowing through the API.
- Treat FIRO-specific data as a variation of the existing dashboard patterns rather than a completely separate stack.
- If the dashboard depends on forecast or reservoir operations concepts, make the labels and filters understandable to non-experts and document any assumptions in the UI or code.
- Prefer server-side filtering and aggregation when possible to keep the frontend lightweight.

## Development workflow
- Before implementing, inspect the relevant existing dashboard and API routes to avoid duplicating logic.
- Keep changes scoped and testable. If a feature needs new data endpoints, add the endpoint and a simple client-side integration path together.
- When changing dependencies, update the relevant package or Python dependency files and consider local container rebuilds if needed.
- Verify the change with the relevant local workflow, such as the API, frontend build, or a targeted manual check in the local environment.
- When in doubt, favor the simplest implementation that can be explained clearly and extended later.

## Constraints

- **Do not modify** `MapComponent.jsx`, existing contexts, or existing dashboard components
- Only append to `api.js`; never change existing functions
- Start simple — no features beyond dataset/variable/timestep selection, tile display, and click popup
- No new npm dependencies without asking
- Plain JSX/JS; no TypeScript
- Match import order, naming, and `useCallback`/`useEffect` patterns from `dashboards/forecast/`