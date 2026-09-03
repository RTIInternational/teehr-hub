import { useCallback } from 'react';

import { useNwmdDashboard, ActionTypes } from '../context/NwmdDashboardContext';
import { apiService } from '../services/api';

// Custom hooks for nwmd dashboard data fetching
export const useNwmdDataFetching = () => {
  const { dispatch } = useNwmdDashboard();

  const loadLeadTimeBinMetrics = useCallback(
    async (filters = {}, table) => {
      try {
        dispatch({ type: ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS });
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { leadTimeBinMetrics: true },
        });

        const metricsData = await apiService.getMetrics({
          table,
          primary_location_id: filters.primary_location_id,
          quarter: filters.quarter,
          configuration: filters.configuration,
          variable: filters.variable,
          threshold: filters.threshold,
          aggMethod: filters.aggMethod,
        });

        const rows = (metricsData?.features || []).map((feature) => feature?.properties || {});

        dispatch({
          type: ActionTypes.SET_LEAD_TIME_BIN_METRICS,
          payload: rows,
        });
        return rows;
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { leadTimeBinMetrics: false },
        });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load lead-time bin metrics: ${error.message}`,
        });
        dispatch({ type: ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS });
        throw error;
      }
    },
    [dispatch]
  );

  // Load location-specific metadata
  const loadLocationMetadata = useCallback(
    async (primaryLocationId) => {
      try {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { metadata: true },
        });
        const metadata = await apiService.getLocationById(primaryLocationId, true);
        dispatch({
          type: ActionTypes.SET_LOCATION_METADATA,
          payload: metadata,
        });
        return metadata;
      } catch (error) {
        console.error('Error loading location metadata:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load location metadata: ${error.message}`,
        });
        dispatch({ type: ActionTypes.CLEAR_LOCATION_METADATA });
        throw error;
      }
    },
    [dispatch]
  );

  return {
    loadLeadTimeBinMetrics,
    loadLocationMetadata,
  };
};

// Custom hook for filter management
export const useNwmdFilters = () => {
  const { state, dispatch } = useNwmdDashboard();

  const updateMapFilters = useCallback(
    (filters) => {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
    },
    [dispatch]
  );

  const updateTimeseriesFilters = useCallback(
    (filters) => {
      dispatch({
        type: ActionTypes.UPDATE_TIMESERIES_FILTERS,
        payload: filters,
      });
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
export const useNwmdLocationSelection = () => {
  const { state, dispatch } = useNwmdDashboard();

  const selectLocation = useCallback(
    (location) => {
      dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
      // Always clear timeseries when location changes (including deselection)
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
      // Clear metrics when location changes
      dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
      // Clear lead-time-bin metrics when location changes
      dispatch({ type: ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS });
    },
    [dispatch]
  );

  return {
    selectedLocation: state.selectedLocation,
    selectLocation,
  };
};
