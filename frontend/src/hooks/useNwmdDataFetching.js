import { useCallback } from 'react';

import { applyAltHypothesisFilter } from '../components/dashboards/nwmd/utils';
import { useNwmdDashboard, ActionTypes } from '../context/NwmdDashboardContext';
import { apiService } from '../services/api';
import { extractTableProperties } from '../shared/utils/ogcTransformers';

// Custom hooks for nwmd dashboard data fetching
export const useNwmdDataFetching = () => {
  const { state, dispatch } = useNwmdDashboard();

  // Load table properties (batch) from queryables
  const loadTableProperties = useCallback(
    async (tables) => {
      try {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { tablePropertiesLoading: true },
        });
        const tableArray = Array.isArray(tables) ? tables : [tables];

        const results = await Promise.all(
          tableArray.map(async (table) => {
            const queryables = await apiService.getQueryables(table);
            return { table, properties: extractTableProperties(queryables) };
          })
        );

        const tableProperties = results.reduce((acc, { table, properties }) => {
          acc[table] = properties;
          return acc;
        }, {});

        dispatch({
          type: ActionTypes.SET_TABLE_PROPERTIES,
          payload: tableProperties,
        });
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load table properties: ${error.message}`,
        });
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { tablePropertiesLoading: false },
        });
      }
    },
    [dispatch]
  );

  // Load locations with filtering
  const loadLocations = useCallback(
    async (filters = {}, table = null) => {
      try {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { locations: true },
        });

        const { altHypothesis95, metricName, ...apiFilters } = filters || {};

        const locations = await apiService.getMetrics({ ...apiFilters, table });
        const filteredLocations = applyAltHypothesisFilter(
          locations,
          metricName || state.mapFilters.metricName,
          altHypothesis95
        );

        dispatch({
          type: ActionTypes.SET_LOCATIONS,
          payload: filteredLocations,
        });
      } catch (error) {
        console.error('useNwmdDataFetching: Error loading locations:', error);
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { locations: false },
        });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load locations: ${error.message}`,
        });
      }
    },
    [dispatch, state.mapFilters.metricName]
  );

  // Load timeseries data
  const loadTimeseries = useCallback(
    async (filters = {}) => {
      try {
        // Clear existing timeseries data first
        dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { timeseries: true },
        });

        const {
          primary_location_id,
          primary = {},
          secondary = {},
          // Backward-compatible flat filter support
          configurations,
          variables,
          variable,
          start_date,
          end_date,
          reference_start_date,
          reference_end_date,
        } = filters;

        const legacyVariables = Array.isArray(variables) ? variables : variable ? [variable] : [];

        const primaryFilters = {
          variables: primary.variables ?? legacyVariables,
          start_date: primary.start_date ?? start_date,
          end_date: primary.end_date ?? end_date,
        };

        const secondaryFilters = {
          configurations: secondary.configurations ?? configurations,
          variables: secondary.variables ?? legacyVariables,
          reference_start_date: secondary.reference_start_date ?? reference_start_date,
          reference_end_date: secondary.reference_end_date ?? reference_end_date,
        };

        if (
          !primary_location_id ||
          !secondaryFilters.configurations?.length ||
          !primaryFilters.variables?.length ||
          !secondaryFilters.variables?.length
        ) {
          throw new Error(
            'Missing required parameters: primary_location_id, primary.variables, secondary.variables, and secondary.configurations are required'
          );
        }

        // Load primary data (USGS observations)
        const primaryData = await apiService.getPrimaryTimeseries(primary_location_id, {
          variable: primaryFilters.variables,
          start_date: primaryFilters.start_date,
          end_date: primaryFilters.end_date,
        });
        dispatch({
          type: ActionTypes.SET_PRIMARY_TIMESERIES,
          payload: primaryData,
        });

        // Load secondary data with multi-value configuration and variable filters
        const secondaryData = await apiService.getSecondaryTimeseries(primary_location_id, {
          variable: secondaryFilters.variables,
          reference_start_date: secondaryFilters.reference_start_date,
          reference_end_date: secondaryFilters.reference_end_date,
          configuration: secondaryFilters.configurations,
        });
        dispatch({
          type: ActionTypes.SET_SECONDARY_TIMESERIES,
          payload: secondaryData,
        });
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { timeseries: false },
        });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load timeseries: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  const loadLeadTimeBinMetrics = useCallback(
    async (filters = {}, table) => {
      try {
        dispatch({ type: ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS });
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { leadTimeBinMetrics: true },
        });

        const metricsData = await apiService.getMetrics({
          table,
          primary_location_id: filters.primary_location_id,
          quarter: filters.quarter,
          configuration: filters.configuration,
          variable: filters.variable,
          threshold: filters.threshold,
          aggMethod: filters.aggMethod,
        });

        const rows = (metricsData?.features || []).map((feature) => feature?.properties || {});

        dispatch({
          type: ActionTypes.SET_LEAD_TIME_BIN_METRICS,
          payload: rows,
        });
        return rows;
      } catch (error) {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { leadTimeBinMetrics: false },
        });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load lead-time bin metrics: ${error.message}`,
        });
        dispatch({ type: ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS });
        throw error;
      }
    },
    [dispatch]
  );

  // Load location-specific metadata
  const loadLocationMetadata = useCallback(
    async (primaryLocationId) => {
      try {
        dispatch({
          type: ActionTypes.SET_LOADING,
          payload: { metadata: true },
        });
        const metadata = await apiService.getLocationById(primaryLocationId, true);
        dispatch({
          type: ActionTypes.SET_LOCATION_METADATA,
          payload: metadata,
        });
        return metadata;
      } catch (error) {
        console.error('Error loading location metadata:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load location metadata: ${error.message}`,
        });
        dispatch({ type: ActionTypes.CLEAR_LOCATION_METADATA });
        throw error;
      }
    },
    [dispatch]
  );

  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await loadTableProperties();
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadTableProperties]);

  return {
    loadTableProperties,
    loadLocations,
    loadTimeseries,
    loadLeadTimeBinMetrics,
    loadLocationMetadata,
    initializeData,
  };
};

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
