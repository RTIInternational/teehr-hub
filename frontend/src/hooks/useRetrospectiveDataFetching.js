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
  
  // Load table properties (batch)
  const loadTableProperties = useCallback(async (tables) => {
    try {
      console.log('Loading table properties for tables:', tables);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { tableProperties: true } });
      const tableProperties = await apiService.getTablePropertiesBatch(Array.isArray(tables) ? tables : [tables]);
      console.log('Table properties loaded:', tableProperties);
      dispatch({ type: ActionTypes.SET_TABLE_PROPERTIES, payload: tableProperties });
      return tableProperties;
    } catch (error) {
      console.error('Error loading table properties:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load table properties: ${error.message}` });
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
      
      // Extract raw properties from GeoJSON features for pivoting
      let locationData = [];
      if (geojsonResponse?.features && geojsonResponse.features.length > 0) {
        // Convert each feature to a row of data
        locationData = geojsonResponse.features.map(feature => {
          return feature.properties || {};
        });
      }
      
      console.log('Raw location data for pivoting:', locationData);
      dispatch({ type: ActionTypes.SET_LOCATION_METRICS, payload: locationData });
      return locationData;
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
        loadTableProperties()
      ]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables, loadTableProperties]);
  
  return {
    loadConfigurations,
    loadVariables,
    loadTableProperties,
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