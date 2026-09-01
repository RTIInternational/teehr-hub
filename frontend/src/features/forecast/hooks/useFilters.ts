import { useCallback } from 'react';

import type { MapFilters } from '@/shared/types/maps';
import type { TimeseriesFilters } from '@/shared/types/timeseries';

import { useDashboard, ActionTypes } from '../DashboardContext';

// Custom hook for filter management

export const useFilters = () => {
  const { state, dispatch } = useDashboard();

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
