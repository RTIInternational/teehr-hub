import { useCallback } from 'react';

import { ActionTypes, useDashboard } from '@/context/NwmdDashboardContext';
import type { MapLocation } from '@/shared/types/locations';

// Custom hook for location selection
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
