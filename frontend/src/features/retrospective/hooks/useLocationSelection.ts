import { useCallback } from 'react';
import { useDashboard, ActionTypes } from '@/features/retrospective/DashboardContext';
import type { MapLocation } from '@/shared/types/locations';

export const useLocationSelection = () => {
  const { state, dispatch } = useDashboard();

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
