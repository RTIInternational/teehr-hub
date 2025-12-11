import { useCallback } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../context/RetrospectiveDashboardContext.jsx';
import { apiService } from '../services/api';

// Custom hooks for retrospective dashboard data fetching
export const useRetrospectiveDataFetching = () => {
  const { dispatch } = useRetrospectiveDashboard();
  
  // Load configurations
  const loadConfigurations = useCallback(async (table) => {
    try {
      console.log('Loading configurations for table:', table);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
      const configurations = await apiService.getConfigurations(table);
      console.log('Configurations loaded:', configurations);
      dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
      return configurations;
    } catch (error) {
      console.error('Error loading configurations:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);
  
  // Load variables
  const loadVariables = useCallback(async (table) => {
    try {
      console.log('Loading variables for table:', table);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
      const variables = await apiService.getVariables(table);
      console.log('Variables loaded:', variables);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
      return variables;
    } catch (error) {
      console.error('Error loading variables:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${error.message}` });
      throw error;
    }
  }, [dispatch]);
  
  // Load metrics
  const loadMetricNames = useCallback(async (table) => {
    try {
      console.log('Loading metrics for table:', table);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { metricsNames: true } });
      const metricNames = await apiService.getMetricNames(table);
      console.log('Metrics loaded:', metricNames);
      dispatch({ type: ActionTypes.SET_METRIC_NAMES, payload: metricNames });
      return metricNames;
    } catch (error) {
      console.error('Error loading metrics:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load metrics: ${error.message}` });
      throw error;
    }
  }, [dispatch]);
  
  // Load locations with filtering
  const loadLocations = useCallback(async (filters = {}, table = null) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: true } });
      
      // Use getMetrics for filtered location data with metrics, or getLocations for basic locations
      const locations = filters.configuration && filters.variable 
        ? await apiService.getMetrics({ ...filters, table })
        : await apiService.getLocations();
      
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: locations });
    } catch (error) {
      console.error('useRetrospectiveDataFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load timeseries data
  const loadTimeseries = useCallback(async (filters = {}) => {
      try {
        // Clear existing timeseries data first
        dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
        dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });
        
        const { location_id, configuration, variable, start_date, end_date, reference_start_date, reference_end_date } = filters;
        
        if (!location_id || !configuration || !variable) {
          throw new Error('Missing required parameters: location_id, configuration, and variable are required');
        }
  
        // Load primary data (simulation data) - uses variable parameter
        const primaryFilters = {
          variable,
          start_date,
          end_date,
          reference_start_date,
          reference_end_date
        };
        const primaryData = await apiService.getPrimaryTimeseries(location_id, primaryFilters);
        dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });
  
        // Load secondary data (observation data) - uses configuration parameter  
        const secondaryFilters = {
          configuration,
          variable,
          start_date,
          end_date,
          reference_start_date,
          reference_end_date
        };
        const secondaryData = await apiService.getSecondaryTimeseries(location_id, secondaryFilters);
        dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
        
      } catch (error) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timeseries: ${error.message}` });
      }
    }, [dispatch]);
  
  // Load location-specific metrics
  const loadLocationMetrics = useCallback(async (locationId, table) => {
    try {
      console.log('Loading metrics for location:', locationId, 'table:', table);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { metricsLoading: true } });
      
      const geojsonResponse = await apiService.getMetrics({ 
        location_id: locationId, 
        table: table 
      });
      
      console.log('Location metrics GeoJSON loaded:', geojsonResponse);
      
      // Extract metrics from GeoJSON features
      let metrics = [];
      if (geojsonResponse?.features && geojsonResponse.features.length > 0) {
        const feature = geojsonResponse.features[0]; // Should only be one feature for a specific location
        const properties = feature.properties || {};
        
        // Convert properties to metrics array, excluding non-metric fields
        const excludeFields = new Set([
          'location_id', 'primary_location_id', 'name', 'location_name',
          'configuration_name', 'variable_name', 'unit_name'
        ]);
        
        metrics = Object.entries(properties)
          .filter(([key, value]) => !excludeFields.has(key) && value !== null && value !== undefined)
          .map(([key, value]) => ({
            metric_name: key,
            metric_value: value
          }));
      }
      
      console.log('Processed metrics:', metrics);
      dispatch({ type: ActionTypes.SET_LOCATION_METRICS, payload: metrics });
      return metrics;
    } catch (error) {
      console.error('Error loading location metrics:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load location metrics: ${error.message}` });
      dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
      throw error;
    }
  }, [dispatch]);
  
  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await Promise.all([
        loadConfigurations(),
        loadVariables(),
        loadMetricNames()
      ]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables, loadMetricNames]);
  
  return {
    loadConfigurations,
    loadVariables,
    loadMetricNames,
    loadLocations,
    loadTimeseries,
    loadLocationMetrics,
    initializeData
  };
};

// Custom hook for filter management
export const useRetrospectiveFilters = () => {
  const { state, dispatch } = useRetrospectiveDashboard();
  
  const updateMapFilters = useCallback((filters) => {
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
  }, [dispatch]);
  
  const updateTimeseriesFilters = useCallback((filters) => {
    dispatch({ type: ActionTypes.UPDATE_TIMESERIES_FILTERS, payload: filters });
  }, [dispatch]);
  
  return {
    mapFilters: state.mapFilters,
    timeseriesFilters: state.timeseriesFilters,
    updateMapFilters,
    updateTimeseriesFilters
  };
};

// Custom hook for location selection
export const useRetrospectiveLocationSelection = () => {
  const { state, dispatch } = useRetrospectiveDashboard();
  
  const selectLocation = useCallback((location) => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    // Always clear timeseries when location changes (including deselection)
    dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
    // Clear metrics when location changes
    dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
  }, [dispatch]);
  
  return {
    selectedLocation: state.selectedLocation,
    selectLocation
  };
};