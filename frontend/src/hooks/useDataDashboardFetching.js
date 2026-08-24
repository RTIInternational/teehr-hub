import { useCallback } from 'react';
import { useDataDashboard, ActionTypes } from '../context/DataDashboardContext.jsx';
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
        )
      };
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: filtered });
      return filtered;
    } catch (error) {
      console.error('useDataDashboardFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locationsLoading: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  // Load configurations table (name, long_name, timeseries_type)
  const loadConfigurationsTable = useCallback(async () => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configsLoading: true } });
      const data = await apiService.getConfigurationsTable();
      // Support array, OGC features, or {items:[]} response shapes
      const configurations = Array.isArray(data)
        ? data
        : Array.isArray(data.items)
          ? data.items
          : (data.features || []).map((f) => f.properties || f);
      dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
      return configurations;
    } catch (error) {
      console.error('useDataDashboardFetching: Error loading configurations:', error);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configsLoading: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  // Select a location
  const selectLocation = useCallback((location) => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
  }, [dispatch]);

  return {
    loadLocations,
    loadConfigurationsTable,
    selectLocation
  };
};
