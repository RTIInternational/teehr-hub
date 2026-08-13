import { useCallback } from 'react';
import { useForecastDashboard, ActionTypes } from '../context/ForecastDashboardContext';
import type { MapLocation } from '../shared/types/locations';
import type { MapFilters } from '../shared/types/maps';
import type { TimeseriesFilters } from '../shared/types/timeseries';

// Custom hook for filter management
export const useForecastFilters = () => {
  const { state, dispatch } = useForecastDashboard();

  const updateMapFilters = useCallback(
    (filters: Partial<MapFilters>) => {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
    },
    [dispatch]
  );

  const updateTimeseriesFilters = useCallback(
    (filters: Partial<TimeseriesFilters>) => {
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
    (location: MapLocation | null) => {
      dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    },
    [dispatch]
  );

  return {
    selectedLocation: state.selectedLocation,
    selectLocation,
  };
};
