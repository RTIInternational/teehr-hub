import { useCallback } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../context/RetrospectiveDashboardContext';
import { apiService } from '../services/api';

// Custom hooks for retrospective dashboard data fetching
export const useRetrospectiveDataFetching = () => {
  const { dispatch } = useRetrospectiveDashboard();

  // Load configurations (distinct values from database)
  const loadConfigurations = useCallback(
    async (table) => {
      try {
        console.log('Loading configurations for table:', table);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
        // Use the new distinct values endpoint
        const configurations = await apiService.getConfigurations(table);
        console.log('Configurations loaded:', configurations);
        dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
        return configurations;
      } catch (error) {
        console.error('Error loading configurations:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load configurations: ${error.message}`,
        });
        throw error;
      }
    },
    [dispatch]
  );

  // Load variables (distinct values from database)
  const loadVariables = useCallback(
    async (table) => {
      try {
        console.log('Loading variables for table:', table);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
        // Use the new distinct values endpoint
        const variables = await apiService.getVariables(table);
        console.log('Variables loaded:', variables);
        dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
        return variables;
      } catch (error) {
        console.error('Error loading variables:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load variables: ${error.message}`,
        });
        throw error;
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
    initializeData,
  };
};

// Custom hook for filter management
export const useRetrospectiveFilters = () => {
  const { state, dispatch } = useRetrospectiveDashboard();

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
export const useRetrospectiveLocationSelection = () => {
  const { state, dispatch } = useRetrospectiveDashboard();

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
