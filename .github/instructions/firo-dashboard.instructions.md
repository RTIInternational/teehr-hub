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

## Backend

### Backend guidance
- Favor the existing API structure under api/src/routes and keep new endpoints consistent with the current OGC-style patterns.
- Reuse existing query helpers, database access utilities, and auth middleware rather than introducing new plumbing.
- When adding data access for FIRO features, make the query parameters explicit and filterable; avoid hard-coded table names unless the workflow is truly one-off.
- Preserve authentication expectations and rate limiting behavior unless the task explicitly requires relaxed access.
- If new backend dependencies are needed, confirm whether they are already available in the API image or Python environment. If not, update the relevant dependency declaration rather than relying on ad hoc installs.
- For local development, assume the data will be served from the existing warehouse setup and make endpoints robust to sparse or partially populated datasets.
- If a new endpoint is required, prefer a narrow resource-focused contract and return structured JSON that the frontend can consume directly.
- For deployment-related work, align new config and environment variables with the existing config pattern and avoid hard-coding hostnames or credentials.

### Backend instructions for dashboard components

#### MapComponent
- Provide a filtered location GeoJSON endpoint for the map layer.
- The endpoint should accept at least:
  - `configuration`
  - `variable`
  - optional metric/threshold/season filters
- Emit GeoJSON features with:
  - `geometry`
  - `properties.primary_location_id`
  - `properties.secondary_location_id`
  - `properties.name`
  - `properties.[selected_metric_field]`
- Keep the contract compatible with the current MapComponent expectations:
  - `state.locations.features` must be an array
  - each feature must be valid GeoJSON
  - the selected metric field must be present in `properties`
- Prefer server-side filtering for `configuration_name`, `variable_name`, and `forecast_lead_time_bin` so the frontend can use map filters without client-side post-processing.
- Ensure the endpoint gracefully returns an empty FeatureCollection when no matching rows exist.

#### TimeseriesComponent
- Add or support endpoints for primary and secondary timeseries retrieval.
- Required query parameters:
  - `primary_location_id`
  - `variables` / `variable`
  - `configurations`
  - `start_date` / `end_date`
  - `reference_start_date` / `reference_end_date`
- Return structured JSON arrays for:
  - primary timeseries: `value_time`, `value`, `variable_name`, `unit_name`, `reference_time`
  - secondary timeseries: `value_time`, `value`, `variable_name`, `configuration_name`, `member`
- Support the current hook behavior:
  - `getPrimaryTimeseries(primary_location_id, filters)`
  - `getSecondaryTimeseries(primary_location_id, filters)`
- Keep the response shape stable so `PlotlyChart` and filtering controls can rely on `state.timeseriesData.primary` and `state.timeseriesData.secondary`.

#### LocationMetrics
- Provide a location-metrics endpoint that accepts:
  - `primary_location_id`
  - `table`
- Return rows or GeoJSON with metric properties so `LocationMetrics` can pivot them.
- Expose metadata through queryables for table properties:
  - `group_by`
  - `metrics`
  - `description`
- For the FIRO tables, ensure table metadata includes:
  - `locations_metrics`
    - metrics like `mean_absolute_error`, `relative_bias`, `pearson_correlation`, `mean_crps_ensemble`, etc.
    - group_by fields such as `season`, `forecast_lead_time_bin`, `threshold`
  - `event_rankings`
    - `event_above_peak_rank`, `peak_value`, `threshold`
  - `event_heatmap`
    - `forecast_lead_time_bin`, `relative_bias`, `root_mean_square_error`, `pearson_correlation`, `threshold`
- Support the metrics panel’s filtering and plot mode by returning raw rows keyed by the group_by fields.

#### General dashboard backend guidance
- Keep backend contracts aligned with `useForecastDataFetching` / `useRetrospectiveDataFetching` expectations.
- Use the current API pattern for queryables and metrics endpoints, not new frontend-only endpoints.
- For FIRO-specific data, map these tables to the existing dashboard flow:
  - `locations_metrics` → map metrics + metric table
  - `event_rankings` / `event_heatmap` → additional metric views if tableProperties expose them
  - `joined_timeseries` → timeseries endpoint data source for paired forecasts/observations
- If a component needs a new field, prefer exposing it via properties on the existing GeoJSON or timeseries payload rather than changing the UI shape.


## Frontend

### Frontend guidance
- Follow the current React layout and routing style in frontend/src and keep dashboard-specific code grouped under the relevant dashboard folder.
- Reuse existing dashboard context providers, hooks, and shared UI components before adding new state management layers.
- Preserve a clear separation between view components, data-loading hooks, and context state. Keep state shape predictable and serializable.
- For map-based UI work, keep filters and controls explicit and easy to reason about. If a map control changes the visible data, make the related state update in the shared dashboard context rather than in local component state only.
- For any new FIRO-specific route or page, add it to the app router in a way that matches the existing auth and layout conventions.
- Keep dashboard layout responsive and consistent with the existing Bootstrap-based styling.
- If new map components, charts, or controls are introduced, make them reusable and keep their props minimal.

### Frontend dashboard components

#### Map component
- Use the existing `MapComponent.jsx` for all map rendering. Do not modify it.
- Should a new map feature be needed, create a new component that wraps `MapComponent.jsx` and adds the desired behavior.
- This map should display the locations available based on a configuration_name and variable_name filter, and allow the user to select a location to view its timeseries and metrics.
- Upon selection, the timeseries and metrics will automatically update to reflect the selected location across the other dashboard components.

#### Timeseries component
- Use the existing `TimeseriesComponent.jsx` for all timeseries rendering. Do not modify it.
- Should a new timeseries feature be needed, create a new component that wraps `TimeseriesComponent.jsx` and adds the desired behavior.
- This timeseries should display the timeseries data for the selected location, configuration_name, and variable_name shown in the map display settings dropdown of the map component. 
- Prior to plotting the timeseries data, there should be filters on the start data and end date for both primary and secondary timeseries data. The user should be able to select the start and end date for both primary and secondary timeseries data, and the timeseries component should update accordingly. This functionality is already present in the Forecast Anaylsis dashboard.

#### Location Analysis component
- This component will be new and is not present in the existing dashboards.
- This component will be responsible for displaying the metrics data for the selected location, configuraiton_name, and variable_name shown in the map display settings dropdown of the map component. In addition to the map display settings dropdown, there will be an additional pair of dropdowns/filters for the user to select the season, threshold, and metric values for the metrics data. The data will plot the metric value against forecast_lead_time_bin for the selected season and threshold. 
  - Unique values to filter on for the season and threshold can be extracted from the locations_metrics table via the 'season' and 'threshold' columns. Note that both contain a 'None' value alongside their string values. The 'None' value should be included in the dropdowns/filters for the user to select.
  - Unique values to filter on for the metric values can be extracted from the locations_metrics table via the column names. All columns aside from [primary_location_id, configuration_name, variable_name, season, forecast_lead_time_bin, threshold, created_at, updated_at] are metric values and should be included in the dropdowns/filters for the user to select. The metric value selected will determine which column is plotted against forecast_lead_time_bin.
- The user should be able to view the filtered data as a table AND as a plot (toggled between the two). The plot should show forecast_lead_time_bin on the x-axis and the selected metric value on the y-axis.

#### Event viewer component
- This component will be new and is not present in the existing dashboards.
- This component will be responsible for displaying the event-based data for the selected location, configuration_name, and variable_name shown in the map display settings dropdown of the map component. In addition to the map display settings dropdown, there will be an additional pair of dropdowns/filters for the user to select which event to view and which lead time to view the ensemble data for.
  - The event viewer will display the observed timeseries for the full event, the ensemble mean timeseries for the full event, and the ensemble members according to the lead time selected in the event viewer reference time dropdown.  

#### Event heatmap component
- This component will be new and is not present in the existing dashboards.
- This component will be responsible for displaying the event-based metrics data for the selected location, configuration_name, and variable_name shown in the map display settings dropdown of the map component. In addition to the map display settings dropdown, there will be an additional pair of dropdowns/filters for the user to select which threshold defines an event and which metric value to view the heatmap for.
- The x-axis will correspond to the events, the y axis will correspond to the forecast lead time bins, and the color will correspond to the metric value selected.

#### Ensemble performance component
- This component will be new and is not present in the existing dashboards.
- This component will be responsible for displaying the range of simulated values for each observed values at various lead times for the selected location, configuration_name, and variable_name shown in the map display settings dropdown of the map component. In addition to the map display settings dropdown, there will be an additional dropdown/filter for the user to select  which lead time to view the ensemble data for.
- The Y axis will be observations and the X axis will be the simulated values. The X values will be shown as a boxplot that shows the range of simulated values for each observed value at the selected lead time.

## FIRO tables
- All data non-core tables that power the FIRO dashboard are included below. Timeseries data utilized in this dashboard is all forecast data, meaning for each reference time there will be several unique timeseries.

### locations_metrics

#### Schema
- primary_location_id: object
- configuration_name: object
- variable_name: object
- season: object
- forecast_lead_time_bin: object
- threshold: object
- mean_absolute_error: float64
- root_mean_square_error: float64
- relative_bias: float64
- pearson_correlation: float64
- nash_sutcliffe_efficiency: float64
- probability_of_detection: float64
- false_alarm_ratio: float64
- critical_success_index: float64
- frequency_bias_index: float64
- FN: float64
- TN: float64
- FP: float64
- TP: float64
- mean_crps_ensemble: float32
- mean_crps_ensemble_skill_score: float64
- mean_brier_score: float32
- mean_brier_score_skill_score: float64
- forecast_lead_time: timedelta64[ns]
- created_at: datetime64[ns]
- updated_at: datetime64[ns]

### event_rankings

#### Schema 
- primary_location_id: object
- configuration_name: object
- variable_name: object
- event_above_id: object
- event_above_peak_rank: float64
- peak_value: float64
- threshold: object
- created_at: datetime64[ns]
- updated_at: datetime64[ns]

### event_heatmap

#### Schema
- primary_location_id: object
- configuration_name: object
- variable_name: object
- event_id: object
- forecast_lead_time_bin: object
- relative_bias: float64
- root_mean_square_error: float64
- pearson_correlation: float64
- threshold: object
- created_at: datetime64[ns]
- updated_at: datetime64[ns]

### joined_timeseries

#### Schema
- primary_location_id: object
- configuration_name: object
- variable_name: object
- unit_name: object
- reference_time: datetime64[ns]
- value_time: datetime64[ns]
- secondary_location_id: object
- primary_value: float32
- secondary_value: float32
- member: object
- month: int32
- year: int32
- water_year: int32
- season: object
- day_of_year: int32
- event_10th: bool
- q_10th: float64
- event_10th_id: object
- event_25th: bool
- q_25th: float64
- event_25th_id: object
- event_50th: bool
- q_50th: float64
- event_50th_id: object
- event_75th: bool
- q_75th: float64
- event_75th_id: object
- event_90th: bool
- q_90th: float64
- event_90th_id: object
- forecast_lead_time_bin: object
- forecast_lead_time: timedelta64[ns]
- created_at: datetime64[ns]
- updated_at: datetime64[ns]