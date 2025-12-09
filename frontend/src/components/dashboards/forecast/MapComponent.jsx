import maplibregl from 'maplibre-gl';
import { useEffect, useRef, useCallback } from 'react';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useForecastDashboard , ActionTypes } from '../../../context/ForecastDashboardContext.jsx';
import { useForecastLocationSelection } from '../../../hooks/useForecastDataFetching';
import { useForecastData } from './useForecastData';
import MapFilterButton from './MapFilterButton.jsx';

const MapComponent = () => {
  const mapContainer = useRef(null);
  const map = useRef(null);
  const popup = useRef(null);
  
  const { state, dispatch } = useForecastDashboard();
  const { selectLocation } = useForecastLocationSelection();
  const { loadLocations } = useForecastData();

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
          layers: []
        },
        center: [-95.7129, 37.0902],
        zoom: 4,
        attributionControl: false
      });
      
      popup.current = new maplibregl.Popup({
        closeButton: true,
        closeOnClick: false,
        maxWidth: '300px'
      });
      
      map.current.on('load', () => {
        // Add OpenStreetMap background
        map.current.addSource('osm', {
          type: 'raster',
          tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256
        });
        
        map.current.addLayer({
          id: 'osm',
          type: 'raster',
          source: 'osm'
        });
        
        dispatch({ type: ActionTypes.SET_MAP_LOADED, payload: true });
      });
      
      // Add click handler for empty space (deselect location)
      map.current.on('click', (e) => {
        // Only deselect if we didn't click on a location feature
        const features = map.current.queryRenderedFeatures(e.point, {
          layers: ['locations-layer']
        });
        
        if (features.length === 0) {
          // Clicked on empty space - deselect location
          selectLocation(null);
          
          // Clear map selection
          if (map.current.getLayer('locations-selected')) {
            map.current.setFilter('locations-selected', ['==', 'location_id', '']);
          }
          
          // Close popup
          popup.current.remove();
        }
      });
      
      map.current.on('error', (e) => {
        console.error('MapLibre error:', e);
        dispatch({ type: ActionTypes.SET_ERROR, payload: `Map error: ${e.error?.message || 'Unknown error'}` });
      });

    } catch (error) {
      console.error('MapComponent: Error creating map:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Map initialization failed: ${error.message}` });
    }
  }, [dispatch, selectLocation]);

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
  
  // Load initial locations when map is ready and filters are available
  useEffect(() => {
    if (state.mapLoaded && state.mapFilters.configuration && state.mapFilters.variable) {
      loadLocations({
        configuration: state.mapFilters.configuration,
        variable: state.mapFilters.variable
      });
    }
  }, [state.mapLoaded, state.mapFilters.configuration, state.mapFilters.variable, loadLocations]);
  
  // Update map when locations change
  useEffect(() => {
    if (!map.current || !state.mapLoaded) return;
    
    // Validate GeoJSON structure
    if (!state.locations || !state.locations.features || !Array.isArray(state.locations.features)) {
      return;
    }
    
    if (state.locations.features.length === 0) {
      return;
    }
    
    const mapInstance = map.current;
    
    // Define event handlers outside try block so they're accessible in cleanup
    const handleLocationClick = (e) => {
      if (e.features.length > 0) {
        const feature = e.features[0];
        const coordinates = feature.geometry.coordinates.slice();
        const properties = feature.properties;
        
        // Update selected location
        selectLocation({
          location_id: properties.location_id,
          name: properties.name,
          coordinates: coordinates
        });
        
        // Update map selection
        mapInstance.setFilter('locations-selected', ['==', 'location_id', properties.location_id]);
        
        // Show popup
        // const metricValue = properties[state.mapFilters.metric];
        // const metricLabel = getMetricLabel(state.mapFilters.metric);
        
        // popup.current
        //   .setLngLat(coordinates)
        //   .setHTML(`
        //     <div style="padding: 8px; font-size: 0.85rem;">
        //       <div style="font-weight: 600; margin-bottom: 4px; color: #495057;">${properties.name}</div>
        //       <div style="margin: 2px 0;"><strong>ID:</strong> ${properties.location_id}</div>
        //       <div style="margin: 2px 0;"><strong>Lat:</strong> ${coordinates[1].toFixed(4)}</div>
        //       <div style="margin: 2px 0;"><strong>Lon:</strong> ${coordinates[0].toFixed(4)}</div>
        //       <div style="margin: 2px 0;"><strong>${metricLabel}:</strong> ${metricValue !== null && metricValue !== undefined ? Number(metricValue).toFixed(3) : 'N/A'}</div>
        //       <div style="margin-top: 4px; font-size: 0.75rem; color: #6c757d;">Click to select</div>
        //     </div>
        //   `)
        //   .addTo(mapInstance);
      }
    };
    
    const handleLocationHover = (e) => {
      mapInstance.getCanvas().style.cursor = 'pointer';
      
      const coordinates = e.features[0].geometry.coordinates.slice();
      const properties = e.features[0].properties;
      
      const metricValue = properties[state.mapFilters.metric];
      const metricLabel = getMetricLabel(state.mapFilters.metric);
      
      popup.current
        .setLngLat(coordinates)
        .setHTML(`
          <div style="padding: 8px; font-size: 0.85rem;">
            <div style="font-weight: 600; margin-bottom: 4px; color: #495057;">${properties.name}</div>
            <div style="margin: 2px 0;"><strong>ID:</strong> ${properties.location_id}</div>
            <div style="margin: 2px 0;"><strong>Lat:</strong> ${coordinates[1].toFixed(4)}</div>
            <div style="margin: 2px 0;"><strong>Lon:</strong> ${coordinates[0].toFixed(4)}</div>
            <div style="margin: 2px 0;"><strong>${metricLabel}:</strong> ${metricValue !== null && metricValue !== undefined ? Number(metricValue).toFixed(3) : 'N/A'}</div>
            <div style="margin-top: 4px; font-size: 0.75rem; color: #6c757d;">Click to select</div>
          </div>
        `)
        .addTo(mapInstance);
    };
    
    const handleLocationLeave = () => {
      mapInstance.getCanvas().style.cursor = '';
      popup.current.remove();
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
      const geojsonData = {
        type: 'FeatureCollection',
        features: state.locations.features.filter(feature => 
          feature.type === 'Feature' && 
          feature.geometry && 
          feature.geometry.coordinates &&
          Array.isArray(feature.geometry.coordinates)
        )
      };
      
      // Unlikely edge case, but handled here.
      if (geojsonData.features.length === 0) {
        console.warn('MapComponent: All location features were filtered out due to invalid format');
        dispatch({ type: ActionTypes.SET_ERROR, payload: 'Location data format is invalid - no valid features found' });
        return;
      }
      
      // Add new source
      mapInstance.addSource('locations', {
        type: 'geojson',
        data: geojsonData
      });
      
      // Get color expression for metric-based coloring
      const colorExpression = getMetricColorExpression(state.mapFilters.metric);
    
    // Add locations layer
    mapInstance.addLayer({
      id: 'locations-layer',
      type: 'circle',
      source: 'locations',
      paint: {
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          4, 6,
          8, 9,
          12, 12
        ],
        'circle-color': colorExpression,
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
        'circle-opacity': 0.8
      }
    });
    
    // Add selected location layer
    mapInstance.addLayer({
        id: 'locations-selected',
        type: 'circle',
        source: 'locations',
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['zoom'],
            4, 8,
            8, 11,
            12, 14
          ],
          'circle-color': '#dc3545',
          'circle-stroke-width': 3,
          'circle-stroke-color': '#ffffff',
          'circle-opacity': 1
        },
        filter: ['==', 'location_id', '']
      });
      
      // Add event listeners
      mapInstance.on('click', 'locations-layer', handleLocationClick);
      mapInstance.on('mouseenter', 'locations-layer', handleLocationHover);
      mapInstance.on('mouseleave', 'locations-layer', handleLocationLeave);
      
    } catch (error) {
      console.error('MapComponent: Error adding locations to map:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to add locations to map: ${error.message}` });
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

  }, [state.locations, state.mapLoaded, state.mapFilters.metric, selectLocation, dispatch]);
  
  return (
    <div className="position-relative h-100 w-100">
      <div ref={mapContainer} className="h-100 w-100">
        {!state.mapLoaded && (
          <div className="position-absolute top-50 start-50 translate-middle text-center">
            <div className="spinner-border text-primary mb-2" role="status">
              <span className="visually-hidden">Loading map...</span>
            </div>
            <div className="small text-muted">
              Initializing MapLibre GL...
            </div>
          </div>
        )}
        
        {/* Map Controls */}
        {state.mapLoaded && <MapFilterButton />}
        
        {/* Map Legend */}
        {state.mapLoaded && <MapLegend />}
      </div>
    </div>
  );
};

// Map Legend Component - shows color scale only
const MapLegend = () => {
  const { state } = useForecastDashboard();
  
  if (!state.mapFilters.metric) return null;
  
  const colorScales = {
    'relative_bias': {
      colors: ['#2166ac', '#5aae61', '#fdd49e', '#d73027'],
      stops: [-1, -0.2, 0.2, 1],
      labels: ['Good', 'Fair', 'Poor', 'Bad']
    },
    'nash_sutcliffe_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1],
      labels: ['Poor', 'Fair', 'Good', 'Excellent']
    },
    'kling_gupta_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1],
      labels: ['Poor', 'Fair', 'Good', 'Excellent']
    },
    'count': {
      colors: ['#ffffcc', '#a1dab4', '#41b6c4', '#225ea8'],
      stops: [0, 100, 500, 1000],
      labels: ['Low', 'Medium', 'High', 'Very High']
    },
    'average': {
      colors: ['#ffffcc', '#c2e699', '#78c679', '#238443'],
      stops: [0, 1, 5, 20],
      labels: ['Low', 'Medium', 'High', 'Very High']
    }
  };
  
  const scale = colorScales[state.mapFilters.metric];
  if (!scale) return null;
  
  const metricLabel = getMetricLabel(state.mapFilters.metric);
  
  return (
    <div 
      className="card position-absolute bottom-0 start-0 m-3 shadow-sm" 
      style={{ minWidth: '150px', maxWidth: '200px', zIndex: 1000, fontSize: '0.85rem' }}
    >
      <div className="card-header py-2">
        <h6 className="card-title mb-0 small">Legend</h6>
      </div>
      <div className="card-body py-2">
        <div className="small"><strong>{metricLabel}</strong></div>
        {scale.colors.map((color, i) => (
          <div key={i} className="d-flex align-items-center mt-1">
            <div 
              style={{
                width: '12px',
                height: '12px',
                backgroundColor: color,
                border: '1px solid #ccc',
                marginRight: '6px'
              }}
            ></div>
            <small>{scale.labels[i]} ({scale.stops[i]})</small>
          </div>
        ))}
      </div>
    </div>
  );
};

// Helper functions
const getMetricColorExpression = (metric) => {
  if (!metric) return '#0d6efd';
  
  const colorScales = {
    'relative_bias': {
      colors: ['#2166ac', '#5aae61', '#fdd49e', '#d73027'],
      stops: [-1, -0.2, 0.2, 1]
    },
    'nash_sutcliffe_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1]
    },
    'kling_gupta_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1]
    },
    'count': {
      colors: ['#ffffcc', '#a1dab4', '#41b6c4', '#225ea8'],
      stops: [0, 100, 500, 1000]
    },
    'average': {
      colors: ['#ffffcc', '#c2e699', '#78c679', '#238443'],
      stops: [0, 1, 5, 20]
    }
  };
  
  const scale = colorScales[metric];
  if (!scale) return '#0d6efd';
  
  return [
    'interpolate',
    ['linear'],
    ['get', metric],
    ...scale.stops.flatMap((stop, i) => [stop, scale.colors[i]])
  ];
};

const getMetricLabel = (metric) => {
  const labels = {
    'count': 'Count',
    'average': 'Average',
    'relative_bias': 'Relative Bias',
    'nash_sutcliffe_efficiency': 'Nash-Sutcliffe Efficiency',
    'kling_gupta_efficiency': 'Kling-Gupta Efficiency'
  };
  return labels[metric] || metric;
};

export default MapComponent;