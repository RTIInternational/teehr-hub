/**
 * SimpleMapPanel — a self-contained MapLibre GL map for the data management
 * dashboard tabs.  It does not use the DataDashboardContext; all state is
 * managed via props.
 *
 * Props
 * -----
 * locations        GeoJSON FeatureCollection of Point features to render as
 *                  circles.  Pass null or empty FeatureCollection to clear.
 * basinLocations   GeoJSON FeatureCollection of Polygon/MultiPolygon features
 *                  to render as a basin fill (50% opacity) below the point layer.
 *                  The map will zoom to fit the basin extent.  Pass null to clear.
 * overlayLocations GeoJSON FeatureCollection of Polygon/MultiPolygon features
 *                  to render as a semi-transparent fill with an outline.
 * overlayVisible   Whether the overlay layer is visible (default true).
 * hoveredOverlayId String id to highlight in the overlay layer.  Must match
 *                  the 'id' property of the overlay features.
 * getPopupHTML     Optional fn(properties, coordinates) => HTML string shown
 *                  on location mouseenter.  Defaults to showing location id.
 * showOverlayToggle  Render a "Boundaries On/Off" button (default false).
 * onOverlayToggle  Callback fn() called when the toggle button is clicked.
 * isActive         When this changes to true the map is resized so it fills
 *                  its container correctly after being hidden (display:none).
 */
import maplibregl from 'maplibre-gl';
import { useEffect, useRef, useState } from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';

const SimpleMapPanel = ({
  locations = null,
  basinLocations = null,
  overlayLocations = null,
  overlayVisible = true,
  hoveredOverlayId = null,
  getPopupHTML = null,
  showOverlayToggle = false,
  onOverlayToggle = null,
  onPointClick = null,
  isActive = true,
}) => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const popup = useRef(null);
  const overPopupRef = useRef(false);
  const popupElementRef = useRef(null);
  const popupListenersBoundRef = useRef(false);
  const popupEnterHandlerRef = useRef(null);
  const popupLeaveHandlerRef = useRef(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // ── 1. Initialize map once ──────────────────────────────────────────────
  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: { version: 8, sources: {}, layers: [] },
      center: [-95.7129, 37.0902],
      zoom: 4,
      attributionControl: false,
    });

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      maxWidth: '320px',
    });

    popupEnterHandlerRef.current = () => {
      overPopupRef.current = true;
    };
    popupLeaveHandlerRef.current = () => {
      overPopupRef.current = false;
      popup.current?.remove();
    };

    map.current.on('load', () => {
      map.current.addSource('osm', {
        type: 'raster',
        tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
      });
      map.current.addLayer({ id: 'osm', type: 'raster', source: 'osm' });
      setMapLoaded(true);
    });

    return () => {
      const popupEl = popupElementRef.current;
      const onEnter = popupEnterHandlerRef.current;
      const onLeave = popupLeaveHandlerRef.current;
      if (popupEl && onEnter && onLeave) {
        popupEl.removeEventListener('mouseenter', onEnter);
        popupEl.removeEventListener('mouseleave', onLeave);
      }
      popupElementRef.current = null;
      popupListenersBoundRef.current = false;
      popupEnterHandlerRef.current = null;
      popupLeaveHandlerRef.current = null;
      map.current?.remove();
      map.current = null;
      setMapLoaded(false);
    };
  }, []);

  // ── 2. Resize when tab becomes active ───────────────────────────────────
  useEffect(() => {
    if (isActive && mapLoaded && map.current) {
      setTimeout(() => map.current?.resize(), 50);
    }
  }, [isActive, mapLoaded]);

  // ── 3. Update point locations layer ────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    // Build valid feature list
    const raw = locations?.features ?? [];
    const valid = raw.filter((f) => {
      const coords = f?.geometry?.coordinates;
      return (
        coords &&
        typeof coords[0] === 'number' &&
        typeof coords[1] === 'number' &&
        isFinite(coords[0]) &&
        isFinite(coords[1]) &&
        coords[0] >= -180 && coords[0] <= 180 &&
        coords[1] >= -90  && coords[1] <= 90
      );
    });

    const bindPopupHoverListeners = () => {
      const el = popup.current?.getElement();
      const onEnter = popupEnterHandlerRef.current;
      const onLeave = popupLeaveHandlerRef.current;
      if (!el || popupListenersBoundRef.current || !onEnter || !onLeave) return;
      el.addEventListener('mouseenter', onEnter);
      el.addEventListener('mouseleave', onLeave);
      popupElementRef.current = el;
      popupListenersBoundRef.current = true;
    };

    // Event handlers (defined here so cleanup can remove exact same refs)
    const handleEnter = (e) => {
      m.getCanvas().style.cursor = 'pointer';
      const feature = e.features[0];
      const coordinates = feature.geometry.coordinates.slice();
      const html = getPopupHTML
        ? getPopupHTML(feature.properties, coordinates)
        : `<div style="padding:6px 8px;font-size:0.85rem;">
             <strong>${feature.properties.name || feature.properties.primary_location_id || ''}</strong>
           </div>`;
      popup.current.setLngLat(coordinates).setHTML(html).addTo(m);
      bindPopupHoverListeners();
    };

    const handleLeave = () => {
      m.getCanvas().style.cursor = '';
      // Delay removal so cursor has time to enter the popup element
      setTimeout(() => {
        if (!overPopupRef.current) popup.current.remove();
      }, 100);
    };

    const handleClick = (e) => {
      if (onPointClick) {
        const feature = e.features[0];
        onPointClick(feature.properties);
      }
    };

    // Remove existing layer / source
    if (m.getLayer('locations-layer')) {
      m.off('mouseenter', 'locations-layer', handleEnter);
      m.off('mouseleave', 'locations-layer', handleLeave);
      m.off('click', 'locations-layer', handleClick);
      m.removeLayer('locations-layer');
    }
    if (m.getSource('locations')) m.removeSource('locations');
    popup.current.remove();

    if (valid.length === 0) return;

    // Ensure overlay layers stay on top
    const beforeLayer = m.getLayer('overlay-fill') ? 'overlay-fill' : undefined;

    m.addSource('locations', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features: valid },
    });
    m.addLayer(
      {
        id: 'locations-layer',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['zoom'],
            4, 6, 8, 9, 12, 12,
          ],
          'circle-color': '#0d6efd',
          'circle-stroke-width': 1,
          'circle-stroke-color': '#000',
          'circle-opacity': 0.8,
        },
      },
      beforeLayer
    );

    m.on('mouseenter', 'locations-layer', handleEnter);
    m.on('mouseleave', 'locations-layer', handleLeave);
    m.on('click', 'locations-layer', handleClick);

    // Fit map to feature extent — flyTo for a single point, fitBounds for many
    if (valid.length === 1) {
      const [lon, lat] = valid[0].geometry.coordinates;
      m.flyTo({ center: [lon, lat], zoom: 10, duration: 700, essential: true });
    } else if (valid.length > 1) {
      const lons = valid.map((f) => f.geometry.coordinates[0]);
      const lats = valid.map((f) => f.geometry.coordinates[1]);
      const bounds = [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ];
      if (isFinite(bounds[0][0])) {
        m.fitBounds(bounds, { padding: 50, duration: 700, maxZoom: 14 });
      }
    }

    return () => {
      try {
        if (m.getLayer && m.getLayer('locations-layer')) {
          m.off('mouseenter', 'locations-layer', handleEnter);
          m.off('mouseleave', 'locations-layer', handleLeave);
          m.off('click', 'locations-layer', handleClick);
          m.removeLayer('locations-layer');
        }
        if (m.getSource && m.getSource('locations')) m.removeSource('locations');
      } catch { /* silent */ }
    };
  }, [mapLoaded, locations, getPopupHTML, onPointClick]);

  // ── 4. Basin polygon layer (dedicated, separate from overlay system) ──────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    // Cleanup helpers
    const removeLayers = () => {
      ['basin-fill', 'basin-line'].forEach((id) => {
        if (m.getLayer(id)) m.removeLayer(id);
      });
      if (m.getSource('basin')) m.removeSource('basin');
    };

    removeLayers();

    const features = basinLocations?.features ?? [];
    if (features.length === 0) return;

    // Only handle polygon geometry types
    const geomType = features[0]?.geometry?.type;
    if (geomType !== 'Polygon' && geomType !== 'MultiPolygon') return;

    // Insert below the point location layer so points stay on top
    const before = m.getLayer('locations-layer') ? 'locations-layer' : undefined;

    m.addSource('basin', { type: 'geojson', data: basinLocations });
    m.addLayer({
      id: 'basin-fill',
      type: 'fill',
      source: 'basin',
      paint: { 'fill-color': '#4a90d9', 'fill-opacity': 0.4 },
    }, before);
    m.addLayer({
      id: 'basin-line',
      type: 'line',
      source: 'basin',
      paint: { 'line-color': '#2c5f8a', 'line-width': 1.5, 'line-opacity': 0.9 },
    }, before);

    // Fit map to basin extent
    const allCoords = [];
    const collectCoords = (geom) => {
      if (!geom) return;
      if (geom.type === 'Polygon') geom.coordinates.forEach((ring) => ring.forEach((c) => allCoords.push(c)));
      else if (geom.type === 'MultiPolygon') geom.coordinates.forEach((poly) => poly.forEach((ring) => ring.forEach((c) => allCoords.push(c))));
    };
    features.forEach((f) => collectCoords(f.geometry));

    if (allCoords.length > 0) {
      const lons = allCoords.map((c) => c[0]);
      const lats = allCoords.map((c) => c[1]);
      m.fitBounds(
        [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
        { padding: 40, duration: 700, maxZoom: 14 }
      );
    }

    return () => {
      try { removeLayers(); } catch { /* silent */ }
    };
  }, [mapLoaded, basinLocations]);

  // ── 5. Update overlay polygon layer ─────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const m = map.current;

    const removeOverlay = () => {
      ['overlay-highlight', 'overlay-fill', 'overlay-line'].forEach((id) => {
        if (m.getLayer(id)) m.removeLayer(id);
      });
      if (m.getSource('overlay')) m.removeSource('overlay');
    };

    removeOverlay();

    const features = overlayLocations?.features;
    if (!features || features.length === 0) return;

    m.addSource('overlay', { type: 'geojson', data: overlayLocations });

    const geomType = features[0]?.geometry?.type;
    const before = m.getLayer('locations-layer') ? 'locations-layer' : undefined;

    if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
      const initVis = overlayVisible ? 'visible' : 'none';
      m.addLayer({
        id: 'overlay-fill',
        type: 'fill',
        source: 'overlay',
        layout: { visibility: initVis },
        paint: { 'fill-color': '#4a90d9', 'fill-opacity': 0.3 },
      }, before);
      m.addLayer({
        id: 'overlay-line',
        type: 'line',
        source: 'overlay',
        layout: { visibility: initVis },
        paint: { 'line-color': '#2c5f8a', 'line-width': 0.8, 'line-opacity': 0.7 },
      }, before);
      m.addLayer({
        id: 'overlay-highlight',
        type: 'fill',
        source: 'overlay',
        layout: { visibility: initVis },
        paint: { 'fill-color': '#ff9800', 'fill-opacity': 0.7 },
        filter: ['==', ['get', 'id'], ''],
      }, before);
    }

    return () => {
      try { removeOverlay(); } catch { /* silent */ }
    };
  }, [mapLoaded, overlayLocations, overlayVisible]);

  // ── 6. Toggle overlay visibility ─────────────────────────────────────────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    const visibility = overlayVisible ? 'visible' : 'none';
    ['overlay-fill', 'overlay-line', 'overlay-highlight'].forEach((id) => {
      if (map.current.getLayer(id)) {
        map.current.setLayoutProperty(id, 'visibility', visibility);
      }
    });
  }, [mapLoaded, overlayVisible]);

  // ── 7. Update hovered overlay highlight filter ────────────────────────────
  useEffect(() => {
    if (!mapLoaded || !map.current) return;
    if (!map.current.getLayer('overlay-highlight')) return;
    const filter = hoveredOverlayId
      ? ['==', ['get', 'id'], hoveredOverlayId]
      : ['==', ['get', 'id'], ''];
    map.current.setFilter('overlay-highlight', filter);
  }, [mapLoaded, hoveredOverlayId]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

      {/* Overlay toggle button */}
      {showOverlayToggle && onOverlayToggle && (
        <button
          className={`btn btn-sm position-absolute ${overlayVisible ? 'btn-primary' : 'btn-outline-secondary bg-white'}`}
          style={{
            bottom: '10px',
            left: '10px',
            zIndex: 1100,
            fontSize: '0.7rem',
            padding: '2px 8px',
            opacity: 0.9,
          }}
          onClick={onOverlayToggle}
          title="Toggle boundary layer"
        >
          Boundaries {overlayVisible ? 'On' : 'Off'}
        </button>
      )}
    </div>
  );
};

export default SimpleMapPanel;
