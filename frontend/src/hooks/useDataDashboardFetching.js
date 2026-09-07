import { useCallback } from 'react';

import { useDataDashboard, ActionTypes } from '../context/DataDashboardContext';
import { apiService } from '../services/api';

export const useDataDashboardFetching = () => {
  const { dispatch } = useDataDashboard();

  // Load locations filtered to usgs- prefix
  const loadLocations = useCallback(async () => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locationsLoading: true } });
      const allLocations = await apiService.getLocations();
      // Filter to only usgs- prefixed locations client-side
      const filtered = {
        ...allLocations,
        features: (allLocations.features || []).filter(
          (f) => f.id?.startsWith('usgs-') || f.properties?.location_id?.startsWith('usgs-')
        ),
      };
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: filtered });
      return filtered;
    } catch (error) {
      console.error('useDataDashboardFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locationsLoading: false } });
      dispatch({
        type: ActionTypes.SET_ERROR,
        payload: `Failed to load locations: ${error.message}`,
      });
      throw error;
    }
  }, [dispatch]);

  // Select a location
  const selectLocation = useCallback(
    (location) => {
      dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    },
    [dispatch]
  );

  return {
    loadLocations,
    selectLocation,
  };
};
