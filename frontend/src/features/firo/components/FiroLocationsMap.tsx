import { useQuery } from '@tanstack/react-query';
import type { FeatureCollection, Point } from 'geojson';
import maplibregl, { type MapLayerMouseEvent } from 'maplibre-gl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Form from 'react-bootstrap/Form';
import Spinner from 'react-bootstrap/Spinner';

import { apiService } from '@/services/api';
import type { MapLocation, LocationsResponse } from '@/shared/types/locations';

import 'maplibre-gl/dist/maplibre-gl.css';

type FiroLocationsMapProps = {
  selectedLocation: MapLocation | null;
  onSelectLocation: (location: MapLocation | null) => void;
};

const FIRO_LOCATION_ALLOWLIST = ['usgs-10011500', 'usgs-10128500', 'usgs-09081600'];

const isLngLatTuple = (coords: unknown): coords is [number, number] =>
  Array.isArray(coords) &&
  coords.length === 2 &&
  typeof coords[0] === 'number' &&
  typeof coords[1] === 'number';

const getLocationFromFeature = (feature: GeoJSON.Feature<GeoJSON.Geometry>) => {
  if (feature.geometry?.type !== 'Point') return null;
  if (!isLngLatTuple(feature.geometry.coordinates)) return null;

  const properties = feature.properties ?? {};
  const primaryLocationId =
    String(properties.primary_location_id ?? properties.id ?? feature.id ?? '').trim() || null;

  if (!primaryLocationId) return null;

  return {
    primary_location_id: primaryLocationId,
    secondary_location_id: properties.secondary_location_id
      ? String(properties.secondary_location_id)
      : undefined,
    name: String(properties.name ?? primaryLocationId),
    coordinates: feature.geometry.coordinates,
  } satisfies MapLocation;
};

const FiroLocationsMap = ({ selectedLocation, onSelectLocation }: FiroLocationsMapProps) => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  const locations = useQuery<LocationsResponse>({
    queryKey: ['firo', 'locations', FIRO_LOCATION_ALLOWLIST],
    queryFn: () =>
      apiService.getLocations(FIRO_LOCATION_ALLOWLIST.length, 0, FIRO_LOCATION_ALLOWLIST),
  });

  const validFeatures = useMemo(() => {
    const features = locations.data?.features ?? [];
    return features.filter((feature) => !!getLocationFromFeature(feature));
  }, [locations.data]);

  const locationsGeoJson = useMemo<FeatureCollection<Point>>(
    () => ({
      type: 'FeatureCollection',
      features: validFeatures.filter(
        (f): f is GeoJSON.Feature<Point> => f.geometry?.type === 'Point'
      ),
    }),
    [validFeatures]
  );

  const matchedLocations = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return [];

    const items: Array<{ feature: GeoJSON.Feature<Point>; location: MapLocation }> = [];
    for (const feature of validFeatures) {
      const location = getLocationFromFeature(feature);
      if (!location || feature.geometry.type !== 'Point') continue;
      items.push({ feature, location });
    }

    return items
      .filter(({ location }) => {
        return (
          location.primary_location_id.toLowerCase().includes(term) ||
          location.name.toLowerCase().includes(term)
        );
      })
      .slice(0, 15);
  }, [searchTerm, validFeatures]);

  const highlightLocation = useCallback((locationId: string | null) => {
    if (!map.current || !map.current.getLayer('locations-selected')) return;

    if (!locationId) {
      map.current.setFilter('locations-selected', ['==', 'id', '__none__']);
      return;
    }

    map.current.setFilter('locations-selected', ['==', ['get', 'id'], locationId]);
  }, []);

  const selectFeature = useCallback(
    (feature: GeoJSON.Feature<GeoJSON.Geometry>, options: { flyTo?: boolean } = {}) => {
      const location = getLocationFromFeature(feature);
      if (!location) return;

      onSelectLocation(location);
      highlightLocation(location.primary_location_id);

      if (options.flyTo !== false && map.current) {
        map.current.flyTo({
          center: location.coordinates,
          zoom: Math.max(map.current.getZoom(), 9),
          duration: 700,
          essential: true,
        });
      }
    },
    [onSelectLocation, highlightLocation]
  );

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {},
        layers: [],
      },
      center: [-105, 40],
      zoom: 4,
      attributionControl: false,
    });

    map.current.on('load', () => {
      if (!map.current) return;

      map.current.addSource('osm', {
        type: 'raster',
        tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '© OpenStreetMap contributors',
      });

      map.current.addLayer({
        id: 'osm-background',
        type: 'raster',
        source: 'osm',
      });

      map.current.addSource('locations', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.current.addLayer({
        id: 'locations-circles',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4, 7, 6, 10, 8],
          'circle-color': '#0d6efd',
          'circle-stroke-width': 1.2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.85,
        },
      });

      map.current.addLayer({
        id: 'locations-selected',
        type: 'circle',
        source: 'locations',
        filter: ['==', 'id', '__none__'],
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 6, 7, 8, 10, 10],
          'circle-color': '#dc3545',
          'circle-stroke-width': 2,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 0.95,
        },
      });

      map.current.on('click', 'locations-circles', (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature) return;
        selectFeature(feature);
      });

      map.current.on('mouseenter', 'locations-circles', () => {
        if (!map.current) return;
        map.current.getCanvas().style.cursor = 'pointer';
      });
      map.current.on('mouseleave', 'locations-circles', () => {
        if (!map.current) return;
        map.current.getCanvas().style.cursor = '';
      });
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [selectFeature]);

  useEffect(() => {
    if (!map.current || !map.current.isStyleLoaded() || !map.current.getSource('locations')) return;
    (map.current.getSource('locations') as maplibregl.GeoJSONSource).setData(locationsGeoJson);
  }, [locationsGeoJson]);

  useEffect(() => {
    highlightLocation(selectedLocation?.primary_location_id ?? null);
  }, [selectedLocation, highlightLocation]);

  return (
    <div className="position-relative h-100">
      {locations.isLoading && (
        <div
          className="position-absolute top-50 start-50 translate-middle bg-white px-3 py-2 rounded shadow-sm"
          style={{ zIndex: 2 }}
        >
          <Spinner animation="border" size="sm" className="me-2" />
          Loading locations...
        </div>
      )}

      {locations.error && (
        <Alert variant="danger" className="m-3 position-absolute" style={{ zIndex: 2 }}>
          Failed to load locations.
        </Alert>
      )}

      <div className="position-absolute top-0 start-0 m-3" style={{ zIndex: 2, width: '320px' }}>
        <Form.Control
          size="sm"
          type="text"
          placeholder="Search by location ID or name"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="shadow-sm"
        />
        {!!searchTerm && matchedLocations.length > 0 && (
          <div
            className="bg-white border rounded shadow-sm mt-1"
            style={{ maxHeight: '220px', overflowY: 'auto' }}
          >
            {matchedLocations.map(({ feature, location }) => (
              <button
                key={`${location.primary_location_id}-${feature.id ?? ''}`}
                className="btn btn-sm text-start w-100 rounded-0 border-0"
                onClick={() => selectFeature(feature)}
              >
                <div className="fw-semibold">{location.name}</div>
                <small className="text-muted">{location.primary_location_id}</small>
              </button>
            ))}
          </div>
        )}
      </div>

      <div ref={mapContainer} className="h-100 w-100" />
    </div>
  );
};

export default FiroLocationsMap;
