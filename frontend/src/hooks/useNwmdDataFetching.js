import { useCallback } from 'react';

import { useNwmdDashboard, ActionTypes } from '../context/NwmdDashboardContext';

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
