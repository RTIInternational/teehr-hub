import maplibregl from 'maplibre-gl';
import { FetchSource, PMTiles, Protocol } from 'pmtiles';
import { useEffect, useRef, useCallback, useState } from 'react';

import 'maplibre-gl/dist/maplibre-gl.css';
import { ensureFreshToken } from '@/features/auth/keycloak';
import { griddedApiService, GRIDDED_API_BASE_URL } from '@/services/griddedApi';
import { usePolygonLayers } from '@/shared/queries/gridded/tiles';
import { useTimesteps } from '@/shared/queries/gridded/timesteps';
import type { PolygonFeatureProps, PolygonFeatures } from '@/shared/types/gridded/tiles';

import { useDashboard, ActionTypes } from '../DashboardContext';
import { OVERLAY_LAYERS } from '../utils/overlayLayers';

// The pmtiles Protocol issues its own fetches, so maplibre's transformRequest
// never sees them — the archive's bearer token has to be attached to a
// FetchSource registered here instead. Protocol.add keys the source by its
// exact URL and silently falls back to an unauthenticated fetch on a mismatch,
// so the registered URL and the pmtiles:// source URL must agree byte for byte.
const pmtilesProtocol = new Protocol();
maplibregl.addProtocol('pmtiles', pmtilesProtocol.tile);

type ArcGisLegendEntry = {
  label: string;
  imageData: string;
  contentType: string;
  width: number;
  height: number;
};

type ArcGisLegendResponse = {
  layers?: Array<{
    layerId: number;
    legend?: ArcGisLegendEntry[];
  }>;
};

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

const escapeHtml = (value: unknown): string =>
  String(value).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c] ?? c);

const POLYGON_LAYER_ID = 'polygon-layer';
const POLYGON_SOURCE_ID = 'polygon-source';
const POLYGON_SELECTED_LAYER_ID = 'polygon-layer-selected';

// A polygon that spans a tile boundary is split across tiles, so the same feature
// can come back once per tile. Collapse those down to one entry per location id.
const dedupePolygonFeatures = (features?: maplibregl.MapGeoJSONFeature[]) => {
  const seen = new Set();
  return (features || []).reduce<PolygonFeatures>((acc, feature) => {
    const props = (feature.properties || {}) as PolygonFeatureProps;
    const key = props.id ?? feature.id;
    if (key !== undefined && key !== null) {
      if (seen.has(key)) return acc;
      seen.add(key);
    }
    acc.push(props);
    return acc;
  }, []);
};

const GriddedMapComponent = () => {
  const { state, dispatch } = useDashboard();
  const { mapFilters, mapLoaded, activeOverlays, activePolygonLayer, selectedLocation } = state;
  const { dataset, variable, timestepIndex, colorRamp, colorRampMin, colorRampMax } = mapFilters;

  const polygonLayers = usePolygonLayers();
  const timesteps = useTimesteps(dataset);

  const mapContainer = useRef<HTMLDivElement | null>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  // Separate popup for polygon hover so it never clobbers the click popup
  const hoverPopup = useRef<maplibregl.Popup | null>(null);
  // Holds the current Bearer token for synchronous use inside transformRequest
  const tokenRef = useRef<string | null>(null);
  // The active archive's FetchSource, so a refreshed token can be pushed into
  // its headers without tearing the source down.
  const polygonFetchSource = useRef<FetchSource | null>(null);
  // Track the click handler so it can be removed when dependencies change
  const clickHandlerRef = useRef<((e: maplibregl.MapMouseEvent) => void | Promise<void>) | null>(
    null
  );

  const currentTimestep = (timesteps.data[timestepIndex] as string | undefined) ?? null;

  // Prime the token so a polygon layer selected before the first tile load
  // still builds its FetchSource with an Authorization header.
  useEffect(() => {
    void ensureFreshToken().then((token) => {
      tokenRef.current = token;
    });
  }, []);

  // Map of overlay id -> array of { label, imageData, contentType, width, height }
  const [overlayLegends, setOverlayLegends] = useState<Record<string, ArcGisLegendEntry[]>>({});
  const fetchedLegends = useRef<Set<string>>(new Set());

  const [legendBlobUrl, setLegendBlobUrl] = useState<string | null>(null);
  // Kept in a ref so the cleanup closure always sees the latest URL to revoke
  const prevLegendBlobUrl = useRef<string | null>(null);

  // Fetch ArcGIS legend JSON for newly-activated overlays that declare a legendUrl.
  useEffect(() => {
    const toFetch = OVERLAY_LAYERS.filter(
      (o) => activeOverlays.includes(o.id) && o.legendUrl && !fetchedLegends.current.has(o.id)
    );
    if (toFetch.length === 0) return;

    toFetch.forEach(async (overlay) => {
      fetchedLegends.current.add(overlay.id);
      const legendUrl = overlay.legendUrl;
      if (!legendUrl) return;
      try {
        const res = await fetch(legendUrl);
        const json: ArcGisLegendResponse = await res.json();
        const layer = json.layers?.find((l) => l.layerId === overlay.legendLayerId);
        const legendEntries = layer?.legend;
        if (legendEntries) {
          setOverlayLegends((prev) => ({ ...prev, [overlay.id]: legendEntries }));
        }
      } catch {
        // Legend fetch failure is non-critical; silently skip.
      }
    });
  }, [activeOverlays]);

  useEffect(() => {
    if (!dataset || !variable || !mapLoaded) {
      if (prevLegendBlobUrl.current) {
        URL.revokeObjectURL(prevLegendBlobUrl.current);
        prevLegendBlobUrl.current = null;
      }
      return;
    }

    const controller = new AbortController();
    let cancelled = false;

    void (async () => {
      const token = await ensureFreshToken();
      const params = new URLSearchParams({
        variables: variable,
        style: colorRamp,
        colorscalerange: `${colorRampMin},${colorRampMax}`,
        belowmincolor: 'transparent',
        f: 'image/png',
        background_color: 'white',
        width: '80', // px
        height: '200', // px
      });
      const url = `${GRIDDED_API_BASE_URL}/api/datasets/${encodeURIComponent(dataset)}/tiles/legend?${params}`;
      try {
        const res = await fetch(url, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          signal: controller.signal,
        });
        if (!res.ok || cancelled) return;

        const blob = await res.blob();
        if (cancelled) return;

        const blobUrl = URL.createObjectURL(blob);
        if (prevLegendBlobUrl.current) URL.revokeObjectURL(prevLegendBlobUrl.current);
        prevLegendBlobUrl.current = blobUrl;
        setLegendBlobUrl(blobUrl);
      } catch {
        // Legend fetch failure is non-critical; silently skip.
      }
    })();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [mapLoaded, dataset, variable, colorRamp, colorRampMin, colorRampMax]);

  // Initialize map once on mount
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    const mapInstance = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {},
        layers: [],
      },
      center: [-105.2, 41.48],
      zoom: 4.6,
      attributionControl: false,
      // Add the Bearer token to every tile request aimed at the xpublish-api.
      // transformRequest is synchronous — tokenRef is kept current by updateTileLayer.
      transformRequest: (url: string) => {
        if (url.startsWith(GRIDDED_API_BASE_URL)) {
          const token = tokenRef.current;
          if (token) return { url, headers: { Authorization: `Bearer ${token}` } };
        }
        return { url };
      },
    });
    map.current = mapInstance;

    popup.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '280px',
    });

    hoverPopup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: '280px',
    });

    mapInstance.on('load', () => {
      mapInstance.addSource('osm', {
        type: 'raster',
        tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
      });
      mapInstance.addLayer({ id: 'osm', type: 'raster', source: 'osm' });

      dispatch({ type: ActionTypes.SET_MAP_LOADED, payload: true });
    });

    mapInstance.on('error', (e: maplibregl.ErrorEvent) => {
      console.error('GriddedMapComponent: MapLibre error:', e);
      // e.sourceId is set for tile/source errors (e.g. 404 for areas with no data); only surface fatal map errors.
      const sourceId = (e as { sourceId?: string }).sourceId;
      if (!sourceId) {
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Map error: ${e.error?.message || 'Unknown error'}`,
        });
      }
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [dispatch]);

  // Update the gridded tile layer when filters change
  const updateTileLayer = useCallback(async () => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded) return;

    // Remove previous layer and source
    if (mapInstance.getLayer('gridded-layer')) mapInstance.removeLayer('gridded-layer');
    if (mapInstance.getSource('gridded-tiles')) mapInstance.removeSource('gridded-tiles');

    if (!dataset || !variable || !currentTimestep) return;

    // Refresh the token before issuing tile requests so transformRequest has a current value.
    tokenRef.current = await ensureFreshToken();
    // transformRequest does not cover pmtiles, so push the refreshed token into
    // the archive's own source as well.
    if (tokenRef.current && polygonFetchSource.current) {
      polygonFetchSource.current.setHeaders(
        new Headers({ Authorization: `Bearer ${tokenRef.current}` })
      );
    }

    const tileUrl = griddedApiService.buildGriddedTileUrl(
      dataset,
      variable,
      currentTimestep,
      colorRamp,
      colorRampMin,
      colorRampMax
    );

    mapInstance.addSource('gridded-tiles', {
      type: 'raster',
      tiles: [tileUrl],
      tileSize: 256,
    });

    mapInstance.addLayer({
      id: 'gridded-layer',
      type: 'raster',
      source: 'gridded-tiles',
      paint: { 'raster-opacity': 0.8 },
    });
  }, [mapLoaded, dataset, variable, currentTimestep, colorRamp, colorRampMin, colorRampMax]);

  useEffect(() => {
    void updateTileLayer();
  }, [updateTileLayer]);

  // Sync external overlay layers to the map whenever the active set changes.
  // Overlays are inserted below gridded-layer so the primary data renders on top.
  useEffect(() => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded) return;

    OVERLAY_LAYERS.forEach(({ id, sourceConfig, layerConfig }) => {
      const isActive = activeOverlays.includes(id);
      const hasLayer = !!mapInstance.getLayer(id);
      const hasSource = !!mapInstance.getSource(id);

      if (isActive && !hasLayer) {
        if (!hasSource) {
          mapInstance.addSource(id, sourceConfig as maplibregl.SourceSpecification);
        }
        const beforeId = mapInstance.getLayer('gridded-layer') ? 'gridded-layer' : undefined;
        mapInstance.addLayer(
          { id, source: id, ...(layerConfig as object) } as maplibregl.LayerSpecification,
          beforeId
        );
      } else if (!isActive && hasLayer) {
        mapInstance.removeLayer(id);
        if (hasSource) mapInstance.removeSource(id);
      }
    });
  }, [mapLoaded, activeOverlays]);

  // Sync polygon layer from pmtiles when activePolygonLayer changes
  useEffect(() => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded) return;

    const polygonLayerId = POLYGON_LAYER_ID;
    const polygonSourceId = POLYGON_SOURCE_ID;

    // Hover shows every polygon under the cursor, so nested features are visible
    // before committing to a click.
    const handlePolygonHover = (e: maplibregl.MapLayerMouseEvent) => {
      const features = dedupePolygonFeatures(e.features);
      if (features.length === 0) return;

      mapInstance.getCanvas().style.cursor = 'pointer';

      const rows = features
        .map(
          (props) => `
            <div style="padding:1px 0;">
              <span style="font-weight:600;">${escapeHtml(props.id ?? 'N/A')}</span>
              <span style="color:#6c757d;"> — ${escapeHtml(props.name ?? 'Unnamed')}</span>
            </div>
          `
        )
        .join('');

      if (hoverPopup.current) {
        hoverPopup.current
          .setLngLat(e.lngLat)
          .setHTML(`
          <div style="padding:8px; font-size:0.8rem;">
            <div style="font-weight:600; margin-bottom:4px; color:#495057;">
              ${features.length} polygon${features.length === 1 ? '' : 's'} here
            </div>
            ${rows}
            <div style="margin-top:4px; font-size:0.7rem; color:#6c757d;">Click to list attributes</div>
          </div>
        `)
          .addTo(mapInstance);
      }
    };

    const handlePolygonLeave = () => {
      mapInstance.getCanvas().style.cursor = '';
      if (hoverPopup.current) hoverPopup.current.remove();
    };

    const removePolygonLayer = () => {
      const polygonOutlineLayerId = `${polygonLayerId}-outline`;

      polygonFetchSource.current = null;
      hoverPopup.current?.remove();

      if (mapInstance.getLayer(POLYGON_SELECTED_LAYER_ID)) {
        mapInstance.removeLayer(POLYGON_SELECTED_LAYER_ID);
      }
      if (mapInstance.getLayer(polygonOutlineLayerId)) {
        mapInstance.removeLayer(polygonOutlineLayerId);
      }
      if (mapInstance.getLayer(polygonLayerId)) {
        mapInstance.removeLayer(polygonLayerId);
      }
      if (mapInstance.getSource(polygonSourceId)) {
        mapInstance.removeSource(polygonSourceId);
      }
    };

    if (!activePolygonLayer) {
      removePolygonLayer();
      return;
    }

    // Find the layer metadata
    const selectedLayer = polygonLayers.data?.find((l) => l.id === activePolygonLayer);
    if (!selectedLayer) {
      removePolygonLayer();
      return;
    }

    try {
      // Remove old layer/source if they exist
      removePolygonLayer();

      // Register an authenticated source before adding it to the map: on a
      // cache miss the Protocol would otherwise build a plain unauthenticated
      // FetchSource for this URL and every range request would 401.
      const archiveUrl = griddedApiService.buildPmtilesUrl(selectedLayer.id);
      const headers = new Headers();
      if (tokenRef.current) headers.set('Authorization', `Bearer ${tokenRef.current}`);
      const fetchSource = new FetchSource(archiveUrl, headers);
      polygonFetchSource.current = fetchSource;
      pmtilesProtocol.add(new PMTiles(fetchSource));

      mapInstance.addSource(polygonSourceId, {
        type: 'vector',
        url: `pmtiles://${archiveUrl}`,
      });

      // Add layer with semi-transparent blue fill and dark outline
      mapInstance.addLayer({
        id: polygonLayerId,
        type: 'fill',
        source: polygonSourceId,
        'source-layer': selectedLayer.source_layer,
        paint: {
          'fill-color': '#3388ff',
          'fill-opacity': 0.5,
          'fill-outline-color': '#1a3d6d',
        },
      });

      // Add an outline layer on top for better visibility
      mapInstance.addLayer({
        id: `${polygonLayerId}-outline`,
        type: 'line',
        source: polygonSourceId,
        'source-layer': selectedLayer.source_layer,
        paint: {
          'line-color': '#1a3d6d',
          'line-width': 2,
        },
      });

      // Highlight for the polygon chosen in the attributes panel. The filter is
      // set to match nothing until a selection is made.
      mapInstance.addLayer({
        id: POLYGON_SELECTED_LAYER_ID,
        type: 'line',
        source: polygonSourceId,
        'source-layer': selectedLayer.source_layer,
        filter: ['==', 'id', ''],
        paint: {
          'line-color': '#dc3545',
          'line-width': 3,
        },
      });

      mapInstance.on('mousemove', polygonLayerId, handlePolygonHover);
      mapInstance.on('mouseleave', polygonLayerId, handlePolygonLeave);
    } catch (err) {
      console.error('GriddedMapComponent: Failed to load polygon layer:', err);
    }

    return () => {
      mapInstance.off('mousemove', polygonLayerId, handlePolygonHover);
      mapInstance.off('mouseleave', polygonLayerId, handlePolygonLeave);
      hoverPopup.current?.remove();
    };
  }, [mapLoaded, activePolygonLayer, polygonLayers.data]);

  // Keep the highlight layer in sync with the polygon chosen in the panel
  useEffect(() => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded || !mapInstance.getLayer(POLYGON_SELECTED_LAYER_ID)) return;

    mapInstance.setFilter(POLYGON_SELECTED_LAYER_ID, [
      '==',
      'id',
      selectedLocation?.primary_location_id ?? '',
    ]);
  }, [mapLoaded, selectedLocation, activePolygonLayer]);

  // Update EDR click handler when active filters change
  useEffect(() => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded) return;

    // Remove previous click handler
    if (clickHandlerRef.current) {
      mapInstance.off('click', clickHandlerRef.current);
    }

    const handleClick = async (e: maplibregl.MapMouseEvent) => {
      const popupInstance = popup.current;
      if (!popupInstance) return;

      const { lng, lat } = e.lngLat;

      // Polygons take precedence over the gridded query. Every polygon under the
      // click — including nested ones — goes to the attributes panel.
      if (activePolygonLayer) {
        const features = mapInstance.queryRenderedFeatures(e.point, {
          layers: [POLYGON_LAYER_ID],
        });
        if (features.length > 0) {
          popupInstance.remove();
          dispatch({
            type: ActionTypes.SET_POLYGON_FEATURES,
            payload: {
              features: dedupePolygonFeatures(features),
              lngLat: { lon: lng, lat },
            },
          });
          return;
        }
      }

      // Otherwise, query the gridded data if available
      if (!dataset || !variable || !currentTimestep) return;

      dispatch({ type: ActionTypes.SET_CLICKED_POINT, payload: { lon: lng, lat } });

      popupInstance
        .setLngLat([lng, lat])
        .setHTML('<div style="padding:6px; font-size:0.8rem;">Loading…</div>')
        .addTo(mapInstance);

      try {
        const value = await griddedApiService.fetchGriddedEdrPoint(
          dataset,
          variable,
          currentTimestep,
          lng,
          lat
        );
        popupInstance.setHTML(`
          <div style="padding:8px; font-size:0.85rem;">
            <div style="font-weight:600; margin-bottom:4px; color:#495057;">${escapeHtml(variable)}</div>
            <div><strong>Value:</strong> ${value !== null && value !== undefined ? (typeof value === 'number' ? value.toFixed(2) : escapeHtml(value)) : 'N/A'}</div>
            <div><strong>Lat:</strong> ${lat.toFixed(4)}</div>
            <div><strong>Lon:</strong> ${lng.toFixed(4)}</div>
            <div style="margin-top:4px; font-size:0.75rem; color:#6c757d;">${escapeHtml(currentTimestep)}</div>
          </div>
        `);
      } catch (err) {
        console.error('GriddedMapComponent: EDR point query failed:', err);
        popupInstance.setHTML(
          '<div style="padding:6px; font-size:0.8rem; color:#dc3545;">Failed to retrieve value.</div>'
        );
      }
    };

    clickHandlerRef.current = handleClick;
    mapInstance.on('click', handleClick);

    return () => {
      if (mapInstance && clickHandlerRef.current) {
        mapInstance.off('click', clickHandlerRef.current);
      }
    };
  }, [mapLoaded, dataset, variable, currentTimestep, activePolygonLayer, dispatch]);

  const activeLegendEntries = OVERLAY_LAYERS.filter(
    (o) => activeOverlays.includes(o.id) && overlayLegends[o.id]
  ).map((o) => ({ label: o.label, entries: overlayLegends[o.id] }));

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
      {(legendBlobUrl || activeLegendEntries.length > 0) && (
        <div
          style={{
            position: 'absolute',
            bottom: '8px',
            right: '8px',
            background: 'rgba(255,255,255,0.92)',
            border: '1px solid #ccc',
            borderRadius: '4px',
            padding: '6px 8px',
            maxHeight: '40vh',
            overflowY: 'auto',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          {legendBlobUrl && (
            <img
              src={legendBlobUrl}
              alt="Legend"
              style={{ display: 'block', marginBottom: activeLegendEntries.length > 0 ? '8px' : 0 }}
            />
          )}
          {activeLegendEntries.map(({ label, entries }) => (
            <div
              key={label}
              style={{ fontSize: '0.72rem', marginBottom: entries.length > 1 ? '6px' : 0 }}
            >
              <div style={{ fontWeight: 600, marginBottom: '2px' }}>{label}</div>
              {entries.map((entry, i) => (
                <div key={i} className="d-flex align-items-center gap-1">
                  <img
                    src={`data:${entry.contentType};base64,${entry.imageData}`}
                    width={entry.width}
                    height={entry.height}
                    alt={entry.label}
                    style={{ flexShrink: 0 }}
                  />
                  <span>{entry.label}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default GriddedMapComponent;
