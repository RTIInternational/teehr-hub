---
description: "Use when creating or modifying the gridded data dashboard that displays icechunk raster tiles via xpublish-tiles and CfEdrPlugin. Covers backend xpublish app structure, new frontend dashboard scaffolding, MapLibre raster tile layer patterns, timestep paging, EDR point-query popup, and dataset/variable selection controls."
applyTo:
  - "frontend/src/components/dashboards/gridded/**"
  - "frontend/src/context/GriddedDashboard*.{js,jsx}"
  - "api/src/**/gridded*.py"
  - "api/src/**/xpublish*.py"
---

# Gridded Data Dashboard

## Backend

The xpublish app serves two plugins from icechunk repos:

| Plugin | Group read | URL pattern (prefixed with `/api`) |
|--------|-----------|------------------------------------|
| `TilesPlugin` | `/pyramids` | `/api/datasets/{dataset_id}/tiles/WebMercatorQuad/{z}/{y}/{x}?variables={variable}&style={color_scale}&colorscalerange={min},{max}&width=256&height=256&f=image%2Fpng&time={iso_datetime}` |
| `CfEdrPlugin` (OGC EDR) | `/raw_data` | `/api/datasets/{dataset_id}/edr/position?coords=POINT({lon} {lat})&parameter-name={variable}&datetime={iso_datetime}&f=geojson` |

**Notes:**
- `{z}/{y}/{x}` — y before x is required by TilesPlugin; do not use `{z}/{x}/{y}`
- `variables` (plural) is the query param name
- `style` accepts a color scale string (e.g., `raster/plasma`); `colorscalerange` is `{min},{max}`
- TilesPlugin auto-discovers and serves the appropriate pyramid level from `/pyramids`; no manual level selection needed

```python
rest = xpublish.Rest(
    datasets=datasets,
    plugins={"tiles": TilesPlugin(), "edr": CfEdrPlugin()},
)
```

Verify the CoverageJSON response schema from the CfEdrPlugin docs or a live response before implementing the popup value parser.

### Python imports

```python
import xpublish
from xpublish_tiles import lib as xpublish_tiles_lib
from xpublish_tiles.xpublish.tiles import TilesPlugin
from xpublish_edr import CfEdrPlugin
```

### Dependencies

Add to `api/pyproject.toml` under `[project] dependencies` (no Dockerfile changes needed — the Dockerfile installs from `pyproject.toml` via `pip install .`):

```toml
"xpublish",
"xpublish-tiles",
"xpublish-edr",
"icechunk",
"xarray",
"zarr",
```

### Custom discovery endpoints

Add these routes directly to `rest.app` so the frontend can populate its selectors:

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api/dataset-variables/{dataset_id}` | `{"variables": ["SWE", ...]}` |
| GET | `/api/datasets/{dataset_id}/coords/time` | `{"values": ["2024-01-01T00:00:00", ...]}` |

### Deployment

This should be a **new, separate service** — not merged into the existing OGC API — because it holds long-lived icechunk sessions and xarray datasets in memory. Mount the xpublish sub-app at `/api` inside a new outer FastAPI app:

```python
api_app = rest.app
# add custom discovery routes to api_app here
outer_app = FastAPI()
outer_app.mount("/api", api_app)
```

Ask the user before creating the new Garden service.

---

## Frontend

### File structure

```
src/components/dashboards/gridded/
  Dashboard.jsx           ← layout + wires context to controls and map
  GriddedMapComponent.jsx ← standalone MapLibre component (no changes to MapComponent.jsx)
  GriddedControls.jsx     ← dataset, variable, timestep pager
  index.js                ← re-exports Dashboard

src/context/
  GriddedDashboardContext.jsx  ← useReducer + Provider + useGriddedDashboard() hook
```

New API functions go at the bottom of `src/services/api.js` (append only).

### Context state shape

```js
{
  datasets: [],         // string[] — available dataset names
  variables: [],        // string[] — variables for selected dataset
  timesteps: [],        // string[] — ISO datetimes for selected dataset+variable
  mapFilters: {
    dataset: null,
    variable: null,
    timestepIndex: 0,   // index into timesteps[]
    colorRamp: null,    // string: color ramp name for raster tile rendering
  },
  mapLoaded: false,
  loading: false,
  error: null,
}
```

Follow the same `useReducer` + Provider + `useGriddedDashboard()` hook pattern as `ForecastDashboardContext`.

### GriddedMapComponent

Standalone component (modeled after `SimpleMapPanel`) that owns its MapLibre instance. Uses `useGriddedDashboard()` directly.

- Initialize with OSM base layer (same pattern as `MapComponent.jsx` lines 104–115)
- On filter change: remove old `gridded-tiles` source/`gridded-layer` layer, then add the new raster source pointing to the tile URL
- Insert the gridded layer above the OSM layer: `mapInstance.addLayer({ ... }, 'osm')`
- Map click → EDR position query → `maplibregl.Popup` showing value, variable, lat/lon

### GriddedControls

Controls matching the style of existing `TimeseriesControls`, placed in the upper-right panel:
1. Dataset `<select>` → dispatches `UPDATE_MAP_FILTERS`; triggers variable reload
2. Variable `<select>` → dispatches `UPDATE_MAP_FILTERS`; triggers timestep reload
3. Prev/Next buttons + timestep label for paging through `state.timesteps`
4. Color ramp `<select>` → stored in `mapFilters.colorRamp`; passed as a raster paint property on the tile layer

### Dashboard layout

Match the exact CSS grid structure used by `dashboards/forecast/Dashboard.jsx` and `dashboards/retrospective/Dashboard.jsx`:

```
gridTemplateColumns: '1fr 1fr'
gridTemplateRows:    'auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.8fr)'
```

| Panel | gridColumn | gridRow | Content |
|-------|-----------|---------|---------|
| Error banner | `1 / -1` | `1 / 2` | Shown only when `state.error` is set |
| Map | `1 / 2` | `1 / 4` (or `2 / 4` with error) | `GriddedMapComponent` |
| Controls | `2 / 3` | `1 / 2` (or `2 / 3` with error) | `GriddedControls` |
| Right-middle (placeholder) | `2 / 3` | `2 / 4` (or `3 / 4` with error) | Reserved for future use |
| Bottom (full-width) | `1 / -1` | `4 / 5` (or `5 / 6` with error) | Reserved for future plots or metrics tables |

Use `DashboardPanel` for all panels. Keep placeholder panels empty with a brief comment.

### Route

Add `/gridded` to `App.jsx` wrapped in `GriddedDashboardProvider`. Ask before modifying `App.jsx`.

---

## Constraints

- **Do not modify** `MapComponent.jsx`, existing contexts, or existing dashboard components
- Only append to `api.js`; never change existing functions
- Start simple — no features beyond dataset/variable/timestep selection, tile display, and click popup
- No new npm dependencies without asking; `maplibre-gl` is already available
- Plain JSX/JS; no TypeScript
- Match import order, naming, and `useCallback`/`useEffect` patterns from `dashboards/forecast/`
