import type { Feature, FeatureCollection, Point } from 'geojson';
import maplibregl, {
  Map,
  Popup,
  type FilterSpecification,
  type MapLayerMouseEvent,
} from 'maplibre-gl';
import React, { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useLocations } from '../../../shared/queries/locations';
import type { MapLocation } from '../../../shared/types/locations';
import type { InvalidFeature, MapMetricClamped, MapState } from '../../../shared/types/maps';
import MapLegend from './MapLegend';
import { getMetricColorExpression, getMetricLabel, isLngLatTuple } from './utils';

type MapComponentProps = {
  state: MapState;
  dispatch: ({ type, payload }: { type: string; payload: unknown }) => void;
  table: string;
  ActionTypes: Record<string, string>;
  selectLocation: (location?: MapLocation) => void;
  MapFilterButton: React.ComponentType;
  showSearch?: boolean;
  overlayLocations?: FeatureCollection;
  overlayVisible?: boolean;
  hoveredOverlayId?: string;
};

const MapComponent = ({
  state,
  dispatch,
  table,
  ActionTypes,
  selectLocation,
  MapFilterButton,
  showSearch = true,
  overlayLocations,
  overlayVisible = true,
  hoveredOverlayId,
}: MapComponentProps) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<Map>(null);
  const popup = useRef<Popup>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const locations = useLocations({
    table,
    configuration: state.mapFilters.configuration,
    variable: state.mapFilters.variable,
  });

  const selectFeatureOnMap = useCallback(
    (feature: Feature<Point>, options: { flyTo?: boolean } = {}) => {
      if (!feature?.geometry?.coordinates || !feature?.properties) return;
      if (!isLngLatTuple(feature.geometry.coordinates)) return;

      const { flyTo = true } = options;
      const coordinates = feature.geometry.coordinates;
      const properties = feature.properties;

      selectLocation({
        primary_location_id: properties.primary_location_id,
        secondary_location_id: properties.secondary_location_id,
        name: properties.name,
        coordinates,
      });

      if (map.current?.getLayer('locations-selected')) {
        map.current.setFilter('locations-selected', [
          '==',
          'primary_location_id',
          properties.primary_location_id,
        ]);
      }

      if (flyTo && map.current) {
        map.current.flyTo({
          center: coordinates,
          zoom: Math.max(map.current.getZoom(), 10),
          duration: 700,
          essential: true,
        });
      }
    },
    [selectLocation]
  );

  const matchedLocations = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    const features = locations.data?.features || [];

    if (!term) return [];

    return features
      .filter((feature: Feature) => {
        const props = feature?.properties || {};
        const primaryId = String(props.primary_location_id || '').toLowerCase();
        const secondaryId = String(props.secondary_location_id || '').toLowerCase();
        const name = String(props.name || '').toLowerCase();

        return primaryId.includes(term) || secondaryId.includes(term) || name.includes(term);
      })
      .slice(0, 15);
  }, [searchTerm, locations.data]);

  // Initialize map function
  const initializeMap = useCallback(() => {
    if (map.current) return; // Initialize map only once

    if (!mapContainer.current) {
      console.error('MapComponent: Map container not found');
      return;
    }

    try {
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
      });

      popup.current = new maplibregl.Popup({
        closeButton: true,
        closeOnClick: false,
        maxWidth: '300px',
      });

      map.current.on('load', () => {
        if (!map.current) return;

        // Add OpenStreetMap background
        map.current.addSource('osm', {
          type: 'raster',
          tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
        });

        map.current.addLayer({
          id: 'osm',
          type: 'raster',
          source: 'osm',
        });

        dispatch({ type: ActionTypes.SET_MAP_LOADED, payload: true });
      });

      // Add click handler for empty space (deselect location)
      map.current.on('click', (e) => {
        if (!map.current) return;

        // Only deselect if we didn't click on a location feature
        const features = map.current.queryRenderedFeatures(e.point, {
          layers: ['locations-layer'],
        });

        if (features.length === 0) {
          // Clicked on empty space - deselect location
          selectLocation();

          // Clear map selection
          if (map.current.getLayer('locations-selected')) {
            map.current.setFilter('locations-selected', ['==', 'primary_location_id', '']);
          }

          // Close popup
          if (popup.current) popup.current.remove();
        }
      });

      map.current.on('error', (e) => {
        console.error('MapLibre error:', e);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Map error: ${e.error?.message || 'Unknown error'}`,
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('MapComponent: Error creating map:', error);
      dispatch({
        type: ActionTypes.SET_ERROR,
        payload: `Map initialization failed: ${message}`,
      });
    }
  }, [dispatch, selectLocation, ActionTypes]);

  // Initialize map
  useEffect(() => {
    initializeMap();

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [initializeMap]);

  // Update map when locations change
  useEffect(() => {
    if (!map.current || !state.mapLoaded) return;

    const mapInstance = map.current;

    // Validate GeoJSON structure
    if (!locations.data || !locations.data?.features || !Array.isArray(locations.data?.features)) {
      return;
    }

    // Clear existing layers when there's no data
    if (locations.data.features.length === 0) {
      // Remove existing layers and sources to clear old data from the map
      if (mapInstance.getLayer('locations-layer')) {
        mapInstance.removeLayer('locations-layer');
      }
      if (mapInstance.getLayer('locations-selected')) {
        mapInstance.removeLayer('locations-selected');
      }
      if (mapInstance.getSource('locations')) {
        mapInstance.removeSource('locations');
      }
      // Close any open popup
      if (popup.current) {
        popup.current.remove();
      }
      return;
    }

    // Define event handlers outside try block so they're accessible in cleanup
    const handleLocationClick = (e: MapLayerMouseEvent) => {
      if (e.features && e.features.length > 0) {
        const feature = e.features[0] as Feature<Point>;
        selectFeatureOnMap(feature, { flyTo: false });
      }
    };

    const handleLocationHover = (e: MapLayerMouseEvent) => {
      mapInstance.getCanvas().style.cursor = 'pointer';

      if (!e.features?.length) return;
      const feature = e.features[0] as Feature<Point>;
      const coordinates = feature.geometry.coordinates;
      const properties = feature.properties;

      if (!properties || !state.mapFilters.metricName || !isLngLatTuple(coordinates)) return;

      const metricValue = properties[state.mapFilters.metricName];
      const metricLabel = getMetricLabel(state.mapFilters.metricName);

      if (popup.current)
        popup.current
          .setLngLat(coordinates)
          .setHTML(
            `
          <div style="padding: 8px; font-size: 0.85rem;">
            <div style="font-weight: 600; margin-bottom: 4px; color: #495057;">${properties.name}</div>
            <div style="margin: 2px 0;"><strong>ID:</strong> ${properties.primary_location_id}</div>
            <div style="margin: 2px 0;"><strong>Lat:</strong> ${coordinates[1].toFixed(4)}</div>
            <div style="margin: 2px 0;"><strong>Lon:</strong> ${coordinates[0].toFixed(4)}</div>
            <div style="margin: 2px 0;"><strong>${metricLabel}:</strong> ${metricValue !== null && metricValue !== undefined ? Number(metricValue).toFixed(3) : 'N/A'}</div>
            <div style="margin-top: 4px; font-size: 0.75rem; color: #6c757d;">Click to select</div>
          </div>
        `
          )
          .addTo(mapInstance);
    };

    const handleLocationLeave = () => {
      mapInstance.getCanvas().style.cursor = '';
      if (popup.current) popup.current.remove();
    };

    try {
      // Remove existing layers and sources
      if (mapInstance.getLayer('locations-layer')) {
        mapInstance.removeLayer('locations-layer');
      }
      if (mapInstance.getLayer('locations-selected')) {
        mapInstance.removeLayer('locations-selected');
      }
      if (mapInstance.getSource('locations')) {
        mapInstance.removeSource('locations');
      }

      // Validate GeoJSON format before adding to map
      const validFeatures: Feature<Point>[] = [];
      const invalidFeatures: InvalidFeature[] = [];
      const clampedMetrics: MapMetricClamped[] = [];

      locations.data.features.forEach((feature: Feature<Point>, index) => {
        // Basic structure validation
        if (
          !feature.type ||
          feature.type !== 'Feature' ||
          !feature.geometry ||
          !feature.geometry.coordinates ||
          !Array.isArray(feature.geometry.coordinates)
        ) {
          invalidFeatures.push({ index, reason: 'invalid structure', feature });
          return;
        }

        const coords = feature.geometry.coordinates;
        const lon = coords[0];
        const lat = coords[1];

        // Coordinate validation
        if (typeof lon !== 'number' || typeof lat !== 'number') {
          invalidFeatures.push({ index, reason: 'non-numeric coordinates', feature });
          return;
        }

        // Check for valid coordinate ranges
        if (lon < -180 || lon > 180) {
          invalidFeatures.push({ index, reason: `longitude out of range: ${lon}`, feature });
          return;
        }

        if (lat < -90 || lat > 90) {
          invalidFeatures.push({ index, reason: `latitude out of range: ${lat}`, feature });
          return;
        }

        // Round coordinates to 8 decimal places (~1mm precision) to avoid varint issues
        // while preserving location accuracy
        feature.geometry.coordinates[0] = Math.round(lon * 1e8) / 1e8;
        feature.geometry.coordinates[1] = Math.round(lat * 1e8) / 1e8;

        // Check for NaN or Infinity
        if (!isFinite(lon) || !isFinite(lat)) {
          invalidFeatures.push({
            index,
            reason: `infinite or NaN coordinates: lon=${lon}, lat=${lat}`,
            feature,
          });
          return;
        }

        // Validate and clamp ALL numeric properties that might cause varint issues
        if (feature.properties) {
          Object.keys(feature.properties).forEach((key) => {
            if (!feature.properties) return;
            const value = feature.properties[key];
            if (typeof value === 'number') {
              if (!isFinite(value)) {
                feature.properties[key] = null;
              } else if (Math.abs(value) > 1e6) {
                if (key === state.mapFilters.metricName) {
                  clampedMetrics.push({
                    index,
                    metric: key,
                    original: value,
                    clamped: Math.sign(value) * 1e6,
                  });
                }
                feature.properties[key] = Math.sign(value) * 1e6;
              }
            }
          });
        }

        validFeatures.push(feature);
      });

      // Log validation results in a single message
      if (invalidFeatures.length > 0 || clampedMetrics.length > 0) {
        console.warn('MapComponent: Data validation results:', {
          totalFeatures: locations.data.features.length,
          validFeatures: validFeatures.length,
          invalidFeatures: invalidFeatures.length,
          clampedMetrics: clampedMetrics.length,
          invalidDetails: invalidFeatures.map((f) => ({ index: f.index, reason: f.reason })),
          clampedDetails: clampedMetrics,
        });
      }

      const geojsonData: FeatureCollection<Point> = {
        type: 'FeatureCollection',
        features: validFeatures,
      };

      // Unlikely edge case, but handled here.
      if (geojsonData.features.length === 0) {
        console.warn('MapComponent: All location features were filtered out due to invalid format');
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: 'Location data format is invalid - no valid features found',
        });
        return;
      }

      // Add new source with error handling
      try {
        mapInstance.addSource('locations', {
          type: 'geojson',
          data: geojsonData,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error('MapComponent: Error adding GeoJSON source:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Map source error: ${message}`,
        });
        return;
      }

      // Get color expression for metric-based coloring
      const colorExpression = getMetricColorExpression(
        state.mapFilters.metricName ?? 'relative_bias'
      );

      // Add locations layer with error handling
      try {
        mapInstance.addLayer({
          id: 'locations-layer',
          type: 'circle',
          source: 'locations',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 8, 9, 12, 12],
            'circle-color': colorExpression,
            'circle-stroke-width': 1,
            'circle-stroke-color': 'black',
            'circle-opacity': 0.8,
          },
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error('MapComponent: Error adding locations layer:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Map layer error: ${message}`,
        });
        return;
      }

      // Add selected location layer with error handling
      try {
        mapInstance.addLayer({
          id: 'locations-selected',
          type: 'circle',
          source: 'locations',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 8, 8, 11, 12, 14],
            'circle-color': colorExpression,
            'circle-stroke-width': 2,
            'circle-stroke-color': 'black',
            'circle-opacity': 1,
          },
          filter: ['==', 'primary_location_id', ''],
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error('MapComponent: Error adding selected locations layer:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Map selected layer error: ${message}`,
        });
        return;
      }

      // Add event listeners
      mapInstance.on('click', 'locations-layer', handleLocationClick);
      mapInstance.on('mouseenter', 'locations-layer', handleLocationHover);
      mapInstance.on('mouseleave', 'locations-layer', handleLocationLeave);

      // If overlay layers already exist, move them below the new locations layers
      if (mapInstance.getLayer('overlay-fill'))
        mapInstance.moveLayer('overlay-fill', 'locations-layer');
      if (mapInstance.getLayer('overlay-line'))
        mapInstance.moveLayer('overlay-line', 'locations-layer');

      // Fit map to the extent of the loaded features
      if (validFeatures.length > 0) {
        const lons = validFeatures.map((f) => f.geometry.coordinates[0]);
        const lats = validFeatures.map((f) => f.geometry.coordinates[1]);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        if (isFinite(minLon) && isFinite(minLat) && isFinite(maxLon) && isFinite(maxLat)) {
          mapInstance.fitBounds(
            [
              [minLon, minLat],
              [maxLon, maxLat],
            ],
            { padding: 50, duration: 700, maxZoom: 14 }
          );
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error('MapComponent: Error adding locations to map:', error);
      dispatch({
        type: ActionTypes.SET_ERROR,
        payload: `Failed to add locations to map: ${message}`,
      });
      return;
    }

    // Cleanup function
    return () => {
      try {
        if (mapInstance && mapInstance.getLayer && mapInstance.getLayer('locations-layer')) {
          mapInstance.off('click', 'locations-layer', handleLocationClick);
          mapInstance.off('mouseenter', 'locations-layer', handleLocationHover);
          mapInstance.off('mouseleave', 'locations-layer', handleLocationLeave);
        }
      } catch {
        // Silent cleanup - don't log in production
      }
    };
  }, [
    locations.data,
    state.mapLoaded,
    state.mapFilters.metricName,
    selectLocation,
    dispatch,
    ActionTypes,
    selectFeatureOnMap,
  ]);

  // Overlay layer (e.g. huc8 polygons) at 50% opacity
  useEffect(() => {
    if (!map.current || !state.mapLoaded) return;
    const mapInstance = map.current;

    const removeOverlay = () => {
      if (mapInstance.getLayer('overlay-highlight')) mapInstance.removeLayer('overlay-highlight');
      if (mapInstance.getLayer('overlay-fill')) mapInstance.removeLayer('overlay-fill');
      if (mapInstance.getLayer('overlay-line')) mapInstance.removeLayer('overlay-line');
      if (mapInstance.getSource('overlay-locations')) mapInstance.removeSource('overlay-locations');
    };

    removeOverlay();

    const features = overlayLocations?.features;
    if (!features || features.length === 0) return;

    mapInstance.addSource('overlay-locations', { type: 'geojson', data: overlayLocations });

    const geomType = features[0]?.geometry?.type;
    const beforeLayer = mapInstance.getLayer('locations-layer') ? 'locations-layer' : undefined;
    if (geomType === 'Polygon' || geomType === 'MultiPolygon') {
      mapInstance.addLayer(
        {
          id: 'overlay-fill',
          type: 'fill',
          source: 'overlay-locations',
          layout: { visibility: 'none' },
          paint: { 'fill-color': '#4a90d9', 'fill-opacity': 0.3 },
        },
        beforeLayer
      );
      mapInstance.addLayer(
        {
          id: 'overlay-line',
          type: 'line',
          source: 'overlay-locations',
          layout: { visibility: 'none' },
          paint: { 'line-color': '#2c5f8a', 'line-width': 0.8, 'line-opacity': 0.7 },
        },
        beforeLayer
      );
      mapInstance.addLayer(
        {
          id: 'overlay-highlight',
          type: 'fill',
          source: 'overlay-locations',
          layout: { visibility: 'none' },
          paint: { 'fill-color': '#ff9800', 'fill-opacity': 0.7 },
          filter: ['any', ['==', ['get', 'id'], ''], ['==', ['id'], -1]],
        },
        beforeLayer
      );
    } else {
      mapInstance.addLayer(
        {
          id: 'overlay-fill',
          type: 'circle',
          source: 'overlay-locations',
          paint: {
            'circle-radius': 5,
            'circle-color': '#4a90d9',
            'circle-opacity': 0.5,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#2c5f8a',
          },
        },
        beforeLayer
      );
    }

    return () => {
      try {
        removeOverlay();
      } catch {
        /* silent */
      }
    };
  }, [overlayLocations, state.mapLoaded]);

  // Update overlay layer visibility
  useEffect(() => {
    if (!map.current || !state.mapLoaded) return;
    const visibility = overlayVisible ? 'visible' : 'none';
    ['overlay-fill', 'overlay-line', 'overlay-highlight'].forEach((id) => {
      if (!map.current) return;
      if (map.current.getLayer(id)) map.current.setLayoutProperty(id, 'visibility', visibility);
    });
  }, [overlayVisible, state.mapLoaded]);

  // Update highlight filter when hovered overlay ID changes
  useEffect(() => {
    if (!map.current || !state.mapLoaded) return;
    if (!map.current.getLayer('overlay-highlight')) return;
    const filter: FilterSpecification = hoveredOverlayId
      ? ['any', ['==', ['get', 'id'], hoveredOverlayId], ['==', ['id'], hoveredOverlayId]]
      : ['any', ['==', ['get', 'id'], ''], ['==', ['id'], -1]];
    map.current.setFilter('overlay-highlight', filter);
  }, [hoveredOverlayId, state.mapLoaded]);

  return (
    <div className="position-relative h-100 w-100">
      <div ref={mapContainer} className="h-100 w-100">
        {!state.mapLoaded && (
          <div className="position-absolute top-50 start-50 translate-middle text-center">
            <div className="spinner-border text-primary mb-2" role="status">
              <span className="visually-hidden">Loading map...</span>
            </div>
            <div className="small text-muted">Initializing MapLibre GL...</div>
          </div>
        )}

        {/* Loading overlay for fetching locations */}
        {state.mapLoaded && locations.isLoading && (
          <div
            className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.7)',
              zIndex: 1000,
              pointerEvents: 'none',
            }}
          >
            <div className="text-center">
              <div className="spinner-border text-primary mb-2" role="status">
                <span className="visually-hidden">Loading locations...</span>
              </div>
              <div className="small text-muted">Loading location data...</div>
            </div>
          </div>
        )}

        {/* Map Controls */}
        {state.mapLoaded && MapFilterButton && <MapFilterButton />}

        {/* Location search */}
        {state.mapLoaded && showSearch && (
          <div
            className="position-absolute top-0 start-0 m-3"
            style={{ zIndex: 1200, width: 'min(380px, calc(100% - 200px))' }}
          >
            <div className="input-group shadow-sm" style={{ height: '38px' }}>
              <span
                className="input-group-text bg-white border-end-0 rounded-start-3"
                aria-hidden="true"
              >
                🔎
              </span>
              <input
                type="text"
                className="form-control border-start-0"
                placeholder="Search by primary ID, secondary ID, or name"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                aria-label="Search map locations"
                style={{ height: '38px' }}
              />
              {searchTerm && (
                <button
                  type="button"
                  className="btn rounded-end-3"
                  onClick={() => setSearchTerm('')}
                  aria-label="Clear search"
                  style={{
                    height: '38px',
                    backgroundColor: '#ffffff',
                    borderColor: '#ced4da',
                    color: '#6c757d',
                  }}
                >
                  Clear
                </button>
              )}
            </div>

            {searchTerm.trim() && (
              <div
                className="list-group shadow-sm"
                style={{ maxHeight: '260px', overflowY: 'auto' }}
              >
                {matchedLocations.length > 0 ? (
                  matchedLocations.map((feature: Feature<Point>) => {
                    const props = feature.properties || {};
                    return (
                      <button
                        key={`${props.primary_location_id}-${props.secondary_location_id || ''}`}
                        type="button"
                        className="list-group-item list-group-item-action"
                        onClick={() => {
                          selectFeatureOnMap(feature, { flyTo: true });
                          setSearchTerm('');
                        }}
                      >
                        <div className="d-flex justify-content-between align-items-start gap-2">
                          <div className="text-start">
                            <div className="fw-semibold">{props.name || 'Unnamed location'}</div>
                            <div className="small text-muted">
                              Primary: {props.primary_location_id || 'N/A'}
                            </div>
                            <div className="small text-muted">
                              Secondary: {props.secondary_location_id || 'N/A'}
                            </div>
                          </div>
                        </div>
                      </button>
                    );
                  })
                ) : (
                  <div className="list-group-item small text-muted">
                    No matching locations found.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Map Legend */}
        {state.mapLoaded && <MapLegend metric={state.mapFilters.metricName} />}
      </div>
    </div>
  );
};

export default MapComponent;
