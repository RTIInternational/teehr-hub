# Plan: Gridded Dashboard Area Query Feature

## TL;DR
Add a polygon draw tool to the MapLibre map (custom click-based, no new dependencies), wire it to the CfEdrPlugin `/area` endpoint, and display summary stats + a Plotly histogram in the currently-empty right-middle and bottom dashboard panels.

---

## Phase 1 — State & API foundation

Steps can be done in parallel.

### 1. Extend `GriddedDashboardContext.jsx`

New state fields:
- `drawMode: false`
- `drawVertices: []`
- `drawnPolygon: null`
- `areaQueryLoading: false`
- `areaQueryError: null`
- `areaQueryResults: null`

New ActionTypes:
- `SET_DRAW_MODE`
- `ADD_DRAW_VERTEX`
- `FINISH_DRAW`
- `CLEAR_DRAW`
- `SET_AREA_QUERY_LOADING`
- `SET_AREA_QUERY_RESULTS`
- `SET_AREA_QUERY_ERROR`

Reducer notes:
- `FINISH_DRAW` builds a GeoJSON Polygon from `drawVertices` (closing the ring) and stores it in `drawnPolygon`; clears `drawVertices` and sets `drawMode: false`.
- `CLEAR_DRAW` resets `drawVertices`, `drawnPolygon`, `areaQueryResults`, and `areaQueryError`.

### 2. Add `fetchGriddedEdrArea()` to `services/api.js`

Endpoint: `/{datasetId}_raw_data/edr/area?coords={WKT}&parameter-name={var}&datetime={time}&f=csv`

Use the existing `griddedApiCall` helper for auth. Add a co-located `parseAreaQueryCsv(csvText, variable)` helper that:
- Splits CSV on newlines, reads the header row to locate the variable column
- Extracts numeric values from that column, filtering NaN/Infinity
- Returns `{ count, mean, min, max, values: number[] }`

WKT format: `POLYGON((lng1 lat1,lng2 lat2,...,lng1 lat1))` — longitude first per WKT convention, first point repeated to close the ring.

---

## Phase 2 — Map draw tool

### 3. Update `GriddedMapComponent.jsx`

**On map `load`**, add persistent draw preview source and layers (always present, updated via `setData`):
- Source `draw-preview` (GeoJSON, starts empty)
- Layer `draw-fill` — Polygon fill, semi-transparent blue (`#3b82f6`, opacity 0.15)
- Layer `draw-line` — LineString + Polygon ring outline, dashed (`[2, 2]`), blue
- Layer `draw-points` — Circle for each placed vertex (radius 5, blue)

**Draw logic** via separate `useEffect` hooks (dependencies include `drawMode`):

- **Click handler**: when `drawMode` is true, dispatch `ADD_DRAW_VERTEX` with `[e.lngLat.lng, e.lngLat.lat]`. Use a `clickDebounceRef` flag (set `true` on `dblclick`, reset after 300ms) to suppress the two synthetic `click` events that fire before `dblclick`.
- **Double-click handler**: dispatch `FINISH_DRAW` with the final coordinate; call `e.preventDefault()` to suppress the map zoom.
- **Escape key**: `keydown` listener on `document`; when `drawMode`, dispatch `CLEAR_DRAW` then `SET_DRAW_MODE(false)`.
- **Cursor**: `map.getCanvas().style.cursor = 'crosshair'` when `drawMode` is on; `''` when off.
- **Interaction guard**: when `drawMode` is true, the existing EDR point-click handler is skipped.

**Preview sync `useEffect`**: whenever `drawVertices` or `drawnPolygon` changes, call `map.getSource('draw-preview').setData(...)` with:
- A Point feature for each vertex
- A LineString feature connecting the vertices (plus back to first vertex if polygon is closed)
- A Polygon feature once drawing is complete

---

## Phase 3 — UI components

Parallel with Phase 2.

### 4. New `GriddedAreaQueryPanel.jsx`

Goes in the **right-middle panel slot** (`gridColumn: '2 / 3'`, `gridRow: '2 / 4'`).

States to render:
- Default: "Draw Area" toggle button
- `drawMode` active: status hint — "Click to add vertices · Double-click to close · Esc to cancel"
- Polygon drawn + `areaQueryLoading`: spinner
- `areaQueryResults` available: compact stats table — Count, Mean, Min, Max — with the variable name as the section title
- `areaQueryError`: inline error message
- Always (when polygon drawn): "Clear" button that dispatches `CLEAR_DRAW`

### 5. New `GriddedAreaHistogram.jsx`

Goes in the **bottom full-width panel slot** (`gridColumn: '1 / -1'`, `gridRow: '4 / 5'`).

- Hidden (returns `null`) when `areaQueryResults` is null
- Plotly bar chart (binned histogram via `type: 'bar'` with manual binning, or `type: 'histogram'`) of `areaQueryResults.values`
- Title: `{variable} — value distribution within drawn area`
- Uses the existing `plotly.js-dist-min` dependency (already installed)

---

## Phase 4 — Dashboard wiring

### 6. Update `Dashboard.jsx`

Add `runAreaQuery` callback (mirrors the `loadVariables` / `loadTimesteps` pattern):
- Builds WKT string from `state.drawnPolygon.coordinates[0]`
- Dispatches `SET_AREA_QUERY_LOADING`
- Calls `griddedApiService.fetchGriddedEdrArea(dataset, variable, currentTimestep, wkt)`
- Dispatches `SET_AREA_QUERY_RESULTS` or `SET_AREA_QUERY_ERROR`

Add `useEffect` to auto-trigger `runAreaQuery` when `drawnPolygon` changes (and is non-null).

Add a second `useEffect` to re-run the query when `timestepIndex` changes if `drawnPolygon` is already set — this keeps the stats/histogram in sync as the user pages through timesteps.

Wire up the previously-empty panel slots:
- Right-middle → `<GriddedAreaQueryPanel />`
- Bottom → `<GriddedAreaHistogram />`

---

## Relevant files

| File | Change |
|------|--------|
| `frontend/src/context/GriddedDashboardContext.jsx` | New state fields + action types + reducer cases |
| `frontend/src/services/api.js` | `fetchGriddedEdrArea`, `parseAreaQueryCsv` |
| `frontend/src/components/dashboards/gridded/GriddedMapComponent.jsx` | Draw sources/layers + click/dblclick/escape handlers + preview sync |
| `frontend/src/components/dashboards/gridded/Dashboard.jsx` | `runAreaQuery` callback + auto-trigger effects + panel wiring |
| `frontend/src/components/dashboards/gridded/GriddedAreaQueryPanel.jsx` | **New** — draw toggle + stats display |
| `frontend/src/components/dashboards/gridded/GriddedAreaHistogram.jsx` | **New** — Plotly value distribution histogram |

**No new npm dependencies.**

---

## Verification checklist

1. `garden deploy` → open gridded dashboard → click Draw Area → click 4+ points on the map → double-click to close → polygon renders on map
2. Stats panel (right-middle) fills with Count / Mean / Min / Max
3. Histogram (bottom) appears with correct variable title
4. Page timestep forward → stats and histogram update automatically
5. Press Esc while drawing → draw mode exits, vertices clear, map returns to normal click behavior
6. Click "Clear" → panels return to placeholder state, polygon removed from map
7. Browser network tab: `/edr/area` request fires with `coords=POLYGON(...)` and `Authorization: Bearer ...` header

---

## Decisions recorded

- Draw-only polygon input (no overlay layer click support for now)
- Stats + histogram for results display
- Custom MapLibre draw (no new npm dependencies)
- `f=csv` response format for in-browser stats parsing
- Auto-re-query on timestep change when a polygon is already drawn

---

## Further considerations

1. **Large response sizes**: A polygon spanning CONUS on a 4km grid could return 10k+ CSV rows. Consider a bounding-box size warning or a row-count cap in a future iteration.
2. **Double-click vertex suppression**: The debounce-flag approach for suppressing the two synthetic `click` events that fire before `dblclick` should be verified across browsers.
