import { useCallback } from 'react';
import { useForecastDashboard, ActionTypes } from '../context/ForecastDashboardContext.jsx';
import { apiService } from '../services/api';

// Custom hooks for forecast dashboard data fetching
export const useForecastDataFetching = () => {
  const { dispatch } = useForecastDashboard();
  
  // Load configurations
  const loadConfigurations = useCallback(async (table) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
      const configurations = await apiService.getConfigurations(table);
      dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load variables
  const loadVariables = useCallback(async (table) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
      const variables = await apiService.getVariables(table);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load metrics
  const loadMetrics = useCallback(async (table) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { metrics: true } });
      const metrics = await apiService.getMetricNames(table);
      dispatch({ type: ActionTypes.SET_METRICS, payload: metrics });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load metrics: ${error.message}` });
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
      console.error('useForecastDataFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load timeseries data
  const loadTimeseries = useCallback(async (filters = {}) => {
    try {
      // Clear existing timeseries data first
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
      dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });
      
      const { location_id, configuration, variable, start_date, end_date, reference_time } = filters;
      
      if (!location_id || !configuration || !variable) {
        throw new Error('Missing required parameters: location_id, configuration, and variable are required');
      }

      // Load primary data (simulation data) - uses variable parameter
      const primaryFilters = {
        variable,
        start_date,
        end_date,
        reference_time
      };
      const primaryData = await apiService.getPrimaryTimeseries(location_id, primaryFilters);
      dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });

      // Load secondary data (observation data) - uses configuration parameter  
      const secondaryFilters = {
        configuration,
        variable,
        start_date,
        end_date,
        reference_time
      };
      const secondaryData = await apiService.getSecondaryTimeseries(location_id, secondaryFilters);
      dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
      
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timeseries: ${error.message}` });
    }
  }, [dispatch]);
  
  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await Promise.all([
        loadConfigurations(),
        loadVariables(),
        loadMetrics()
      ]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables, loadMetrics]);
  
  return {
    loadConfigurations,
    loadVariables,
    loadMetrics,
    loadLocations,
    loadTimeseries,
    initializeData
  };
};

// Custom hook for filter management
export const useForecastFilters = () => {
  const { state, dispatch } = useForecastDashboard();
  
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
export const useForecastLocationSelection = () => {
  const { state, dispatch } = useForecastDashboard();
  
  const selectLocation = useCallback((location) => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    // Always clear timeseries when location changes (including deselection)
    dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
  }, [dispatch]);
  
  return {
    selectedLocation: state.selectedLocation,
    selectLocation
  };
};