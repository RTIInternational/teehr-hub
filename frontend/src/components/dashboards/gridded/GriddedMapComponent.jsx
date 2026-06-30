import maplibregl from 'maplibre-gl';
import { useEffect, useRef, useCallback } from 'react';
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
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Map error: ${e.error?.message || 'Unknown error'}` });
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

  return (
    <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />
  );
};

export default GriddedMapComponent;
