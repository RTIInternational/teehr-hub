import { useCallback } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../context/RetrospectiveDashboardContext';
import type { MapLocation } from '../shared/types/locations';
import type { MapFilters } from '../shared/types/maps';
import type { TimeseriesFiltersFlat } from '../shared/types/timeseries';

// Custom hook for filter management
export const useRetrospectiveFilters = () => {
  const { state, dispatch } = useRetrospectiveDashboard();

  const updateMapFilters = useCallback(
    (filters: Partial<MapFilters>) => {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
    },
    [dispatch]
  );

  const updateTimeseriesFilters = useCallback(
    (filters: Partial<TimeseriesFiltersFlat>) => {
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
