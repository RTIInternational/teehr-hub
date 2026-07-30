import maplibregl from 'maplibre-gl';
import { useEffect, useRef, useCallback, useState } from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useGriddedDashboard, ActionTypes } from '../../../context/GriddedDashboardContext.jsx';
import { griddedApiService, GRIDDED_API_BASE_URL } from '../../../services/api.js';
import { ensureFreshToken } from '../../../auth/keycloak.js';
import { OVERLAY_LAYERS } from './overlayLayers.js';

const GriddedMapComponent = () => {
  const { state, dispatch } = useGriddedDashboard();
  const { mapFilters, mapLoaded, activeOverlays } = state;
  const { dataset, variable, timestepIndex, colorRamp, colorRampMin, colorRampMax } = mapFilters;

  const mapContainer = useRef(null);
  const map = useRef(null);
  const popup = useRef(null);
  // Holds the current Bearer token for synchronous use inside transformRequest
  const tokenRef = useRef(null);
  // Track the click handler so it can be removed when dependencies change
  const clickHandlerRef = useRef(null);

  const currentTimestep = state.timesteps[timestepIndex] ?? null;

  // Map of overlay id -> array of { label, imageData, contentType, width, height }
  const [overlayLegends, setOverlayLegends] = useState({});
  const fetchedLegends = useRef(new Set());

  // Fetch ArcGIS legend JSON for newly-activated overlays that declare a legendUrl.
  useEffect(() => {
    const toFetch = OVERLAY_LAYERS.filter(
      (o) => activeOverlays.includes(o.id) && o.legendUrl && !fetchedLegends.current.has(o.id),
    );
    if (toFetch.length === 0) return;

    toFetch.forEach(async (overlay) => {
      fetchedLegends.current.add(overlay.id);
      try {
        const res = await fetch(overlay.legendUrl);
        const json = await res.json();
        const layer = json.layers?.find((l) => l.layerId === overlay.legendLayerId);
        if (layer?.legend) {
          setOverlayLegends((prev) => ({ ...prev, [overlay.id]: layer.legend }));
        }
      } catch {
        // Legend fetch failure is non-critical; silently skip.
      }
    });
  }, [activeOverlays]);

  // Initialize map once on mount
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {},
        layers: [],
      },
      center: [-95.7129, 37.0902],
      zoom: 4,
      attributionControl: false,
      // Add the Bearer token to every tile request aimed at the xpublish-api.
      // transformRequest is synchronous — tokenRef is kept current by updateTileLayer.
      transformRequest: (url) => {
        if (url.startsWith(GRIDDED_API_BASE_URL)) {
          const token = tokenRef.current;
          if (token) return { url, headers: { Authorization: `Bearer ${token}` } };
        }
        return { url };
      },
    });

    popup.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '280px',
    });

    map.current.on('load', () => {
      map.current.addSource('osm', {
        type: 'raster',
        tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
      });
      map.current.addLayer({ id: 'osm', type: 'raster', source: 'osm' });

      dispatch({ type: ActionTypes.SET_MAP_LOADED, payload: true });
    });

    map.current.on('error', (e) => {
      console.error('GriddedMapComponent: MapLibre error:', e);
      // e.sourceId is set for tile/source errors (e.g. 404 for areas with no data); only surface fatal map errors.
      if (!e.sourceId) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: `Map error: ${e.error?.message || 'Unknown error'}` });
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

    const tileUrl = griddedApiService.buildGriddedTileUrl(
      dataset,
      variable,
      currentTimestep,
      colorRamp,
      colorRampMin,
      colorRampMax,
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
    updateTileLayer();
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
        if (!hasSource) mapInstance.addSource(id, sourceConfig);
        const beforeId = mapInstance.getLayer('gridded-layer') ? 'gridded-layer' : undefined;
        mapInstance.addLayer({ id, source: id, ...layerConfig }, beforeId);
      } else if (!isActive && hasLayer) {
        mapInstance.removeLayer(id);
        if (hasSource) mapInstance.removeSource(id);
      }
    });
  }, [mapLoaded, activeOverlays]);

  // Update EDR click handler when active filters change
  useEffect(() => {
    const mapInstance = map.current;
    if (!mapInstance || !mapLoaded) return;

    // Remove previous click handler
    if (clickHandlerRef.current) {
      mapInstance.off('click', clickHandlerRef.current);
    }

    const handleClick = async (e) => {
      if (!dataset || !variable || !currentTimestep) return;

      const { lng, lat } = e.lngLat;

      dispatch({ type: ActionTypes.SET_CLICKED_POINT, payload: { lon: lng, lat } });

      popup.current
        .setLngLat([lng, lat])
        .setHTML('<div style="padding:6px; font-size:0.8rem;">Loading…</div>')
        .addTo(mapInstance);

      try {
        const value = await griddedApiService.fetchGriddedEdrPoint(
          dataset,
          variable,
          currentTimestep,
          lng,
          lat,
        );
        popup.current.setHTML(`
          <div style="padding:8px; font-size:0.85rem;">
            <div style="font-weight:600; margin-bottom:4px; color:#495057;">${variable}</div>
            <div><strong>Value:</strong> ${value !== null && value !== undefined ? (typeof value === 'number' ? value.toFixed(2) : value) : 'N/A'}</div>
            <div><strong>Lat:</strong> ${lat.toFixed(4)}</div>
            <div><strong>Lon:</strong> ${lng.toFixed(4)}</div>
            <div style="margin-top:4px; font-size:0.75rem; color:#6c757d;">${currentTimestep}</div>
          </div>
        `);
      } catch (err) {
        console.error('GriddedMapComponent: EDR point query failed:', err);
        popup.current.setHTML('<div style="padding:6px; font-size:0.8rem; color:#dc3545;">Failed to retrieve value.</div>');
      }
    };

    clickHandlerRef.current = handleClick;
    mapInstance.on('click', handleClick);

    return () => {
      if (mapInstance && clickHandlerRef.current) {
        mapInstance.off('click', clickHandlerRef.current);
      }
    };
  }, [mapLoaded, dataset, variable, currentTimestep]);

  const activeLegendEntries = OVERLAY_LAYERS
    .filter((o) => activeOverlays.includes(o.id) && overlayLegends[o.id])
    .map((o) => ({ label: o.label, entries: overlayLegends[o.id] }));

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
      {activeLegendEntries.length > 0 && (
        <div
          style={{
            position: 'absolute',
            bottom: '28px',
            right: '8px',
            background: 'rgba(255,255,255,0.92)',
            border: '1px solid #ccc',
            borderRadius: '4px',
            padding: '6px 8px',
            fontSize: '0.72rem',
            maxHeight: '40vh',
            overflowY: 'auto',
            pointerEvents: 'none',
            zIndex: 1,
          }}
        >
          {activeLegendEntries.map(({ label, entries }) => (
            <div key={label} style={{ marginBottom: entries.length > 1 ? '6px' : 0 }}>
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
