import { useCallback } from 'react';
import { useForecastDashboard, ActionTypes } from '../context/ForecastDashboardContext';
import { apiService } from '../services/api';

// Custom hooks for forecast dashboard data fetching
export const useForecastDataFetching = () => {
  const { dispatch } = useForecastDashboard();

  // Load configurations (distinct values from database)
  const loadConfigurations = useCallback(
    async (table) => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
        // Use the new distinct values endpoint
        const configurations = await apiService.getConfigurations(table);
        dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load configurations: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  // Load variables (distinct values from database)
  const loadVariables = useCallback(
    async (table) => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
        // Use the new distinct values endpoint
        const variables = await apiService.getVariables(table);
        dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load variables: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  // Load primary_timeseries variable names and expand them using DURATION_NAME_TO_ISO
  const loadPrimaryVariables = useCallback(async () => {
    try {
      const rawVariables = await apiService.getVariables('primary_timeseries');
      dispatch({ type: ActionTypes.SET_PRIMARY_VARIABLES, payload: rawVariables });
    } catch (error) {
      dispatch({
        type: ActionTypes.SET_ERROR,
        payload: `Failed to load primary variables: ${error.message}`,
      });
    }
  }, [dispatch]);

  // Load locations with filtering
  const loadLocations = useCallback(
    async (filters = {}, table = null) => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: true } });

        // Use getMetrics for filtered location data with metrics, or getLocations for basic locations
        const locations =
          filters.configuration && filters.variable
            ? await apiService.getMetrics({ ...filters, table })
            : await apiService.getLocations();

        dispatch({ type: ActionTypes.SET_LOCATIONS, payload: locations });
      } catch (error) {
        console.error('useForecastDataFetching: Error loading locations:', error);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: false } });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load locations: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await Promise.all([loadConfigurations(), loadVariables()]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables]);

  return {
    loadConfigurations,
    loadVariables,
    loadPrimaryVariables,
    loadLocations,
    initializeData,
  };
};

// Custom hook for filter management
export const useForecastFilters = () => {
  const { state, dispatch } = useForecastDashboard();

  const updateMapFilters = useCallback(
    (filters) => {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
    },
    [dispatch]
  );

  const updateTimeseriesFilters = useCallback(
    (filters) => {
      dispatch({ type: ActionTypes.UPDATE_TIMESERIES_FILTERS, payload: filters });
    },
    [dispatch]
  );

  return {
    mapFilters: state.mapFilters,
    timeseriesFilters: state.timeseriesFilters,
    updateMapFilters,
    updateTimeseriesFilters,
  };
};

// Custom hook for location selection
export const useForecastLocationSelection = () => {
  const { state, dispatch } = useForecastDashboard();

  const selectLocation = useCallback(
    (location) => {
      dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
      // Always clear timeseries when location changes (including deselection)
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
    },
    [dispatch]
  );

  return {
    selectedLocation: state.selectedLocation,
    selectLocation,
  };
};
