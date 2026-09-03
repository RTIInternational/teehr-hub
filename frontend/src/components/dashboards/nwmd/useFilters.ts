import { useCallback } from 'react';

import type { TimeseriesFilters } from '@/shared/types/timeseries';

import { useDashboard, ActionTypes } from '../../../context/NwmdDashboardContext';
import type { NwmdMapFilters } from './types/maps';

// Custom hook for filter management

export const useFilters = () => {
  const { state, dispatch } = useDashboard();

  const updateMapFilters = useCallback(
    (filters: Partial<NwmdMapFilters>) => {
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
