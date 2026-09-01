import { useCallback } from 'react';

import { useDashboard, ActionTypes } from '@/features/retrospective/DashboardContext';
import type { MapFilters } from '@/shared/types/maps';
import type { TimeseriesFilters } from '@/shared/types/timeseries';

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
