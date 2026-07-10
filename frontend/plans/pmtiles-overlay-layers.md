# PMTiles Overlay Layer Support — Re-implementation Plan

This plan documents changes that were made to support reading and displaying PMTiles vector overlays in the gridded data dashboard, then reverted. Use this file to re-implement the feature.

## Overview

The goal is to render vector overlay layers stored as `.pmtiles` files in MinIO directly in the MapLibre map, without a separate tile server. The `pmtiles` npm package provides a MapLibre protocol handler that translates `pmtiles://…` source URLs into byte-range requests against the object store.

The initial use-case was a HUC12 basin boundary overlay sourced from `s3://warehouse/vector-tiles/huc12_basins.pmtiles`.

---

## File Changes Required

### 1. `frontend/package.json`

Add the `pmtiles` dependency:

```diff
+    "pmtiles": "^4.4.1",
```

Run `npm install` after editing (updates `package-lock.json` automatically).

---

### 2. `frontend/src/components/dashboards/gridded/GriddedMapComponent.jsx`

Import the `Protocol` class and register it as a MapLibre protocol **once at module load**, before the map is instantiated:

```diff
 import maplibregl from 'maplibre-gl';
+import { Protocol } from 'pmtiles';
 import { useEffect, useRef, useCallback, useState } from 'react';
 import 'maplibre-gl/dist/maplibre-gl.css';
+
+// Register once at module load.
+maplibregl.addProtocol('pmtiles', new Protocol().tile);
```

The protocol must be registered before any map instance is created that uses a `pmtiles://` source URL.

---

### 3. `frontend/src/components/dashboards/gridded/overlayLayers.js`

Read the MinIO base URL from the environment and add the HUC12 basins layer definition at the top of `OVERLAY_LAYERS`:

```diff
+const MINIO_URL = import.meta.env.VITE_MINIO_URL || 'http://minio:9000';
+
 export const OVERLAY_LAYERS = [
+  {
+    id: 'huc12-basins',
+    label: 'HUC12 Basins',
+    sourceConfig: {
+      type: 'vector',
+      url: `pmtiles://${MINIO_URL}/warehouse/vector-tiles/huc12_basins.pmtiles`,
+    },
+    layerConfig: {
+      type: 'fill',
+      'source-layer': 'huc12_basins',
+      paint: {
+        'fill-color': 'transparent',
+        'fill-outline-color': '#1a6faf',
+        'fill-opacity': 0.8,
+      },
+    },
+  },
   {
     id: 'nws-cpc-6-10-day',
```

The `source-layer` value (`huc12_basins`) must match the layer name baked into the `.pmtiles` file. Verify with `pmtiles show` or the `pmtiles` CLI if unsure.

---

### 4. Environment variable: `VITE_MINIO_URL`

The overlay layer source URL is built from `VITE_MINIO_URL`. This env var must be injected in every deployment context.

#### `frontend/garden.yaml` (Garden build-time env)

```diff
     VITE_KEYCLOAK_CLIENT_ID: "teehr-frontend"
+    VITE_MINIO_URL: "https://minio.${var.hostname}"
```

#### `frontend/manifests/configmap-dev.yaml.tpl`

```diff
   VITE_ALLOWED_HOSTS: "dashboards.${var.hostname}"
+  VITE_MINIO_URL: "https://minio.${var.hostname}"
```

> Note: remove the missing newline at end of the existing last line while editing.

#### `frontend/manifests/deployment-dev.yaml.tpl`

Add a new env entry after the `VITE_KEYCLOAK_CLIENT_ID` block:

```diff
             configMapKeyRef:
               name: teehr-frontend-config
               key: VITE_KEYCLOAK_CLIENT_ID
+        - name: VITE_MINIO_URL
+          valueFrom:
+            configMapKeyRef:
+              name: teehr-frontend-config
+              key: VITE_MINIO_URL
```

---

## Data Prerequisites

- The file `huc12_basins.pmtiles` must exist at `s3://warehouse/vector-tiles/huc12_basins.pmtiles` (MinIO bucket `warehouse`, key `vector-tiles/huc12_basins.pmtiles`).
- The source file used to create it is `data/huc12_basins.geojsonseq`. The notebook `data/create_vector_map_tiles.ipynb` contains the Tippecanoe command used to generate the pmtiles file.
- The MinIO bucket/path must be publicly readable (or the browser must send auth headers — the pmtiles protocol handler supports custom fetch options if needed).

---

## CORS Consideration

The browser fetches byte-ranges directly from the MinIO URL. MinIO must return the appropriate CORS headers for the frontend origin. Confirm that the MinIO `warehouse` bucket CORS policy allows `GET` with `Range` headers from the frontend origin.

---

## Testing

1. Run the dev frontend with `VITE_MINIO_URL` pointing at local MinIO.
2. Open the gridded dashboard and enable the "HUC12 Basins" overlay checkbox.
3. Verify basin boundaries appear on the map with a blue outline and transparent fill.
4. Confirm no CORS errors in the browser console.
