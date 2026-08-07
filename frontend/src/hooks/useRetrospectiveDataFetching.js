import { useCallback } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../context/RetrospectiveDashboardContext';
import { apiService } from '../services/api';
import { toPrimaryVariableName } from '../utils/durationUtils';

// Custom hooks for retrospective dashboard data fetching
export const useRetrospectiveDataFetching = () => {
  const { dispatch } = useRetrospectiveDashboard();

  // Load configurations (distinct values from database)
  const loadConfigurations = useCallback(
    async (table) => {
      try {
        console.log('Loading configurations for table:', table);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
        // Use the new distinct values endpoint
        const configurations = await apiService.getConfigurations(table);
        console.log('Configurations loaded:', configurations);
        dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
        return configurations;
      } catch (error) {
        console.error('Error loading configurations:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load configurations: ${error.message}`,
        });
        throw error;
      }
    },
    [dispatch]
  );

  // Load variables (distinct values from database)
  const loadVariables = useCallback(
    async (table) => {
      try {
        console.log('Loading variables for table:', table);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
        // Use the new distinct values endpoint
        const variables = await apiService.getVariables(table);
        console.log('Variables loaded:', variables);
        dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
        return variables;
      } catch (error) {
        console.error('Error loading variables:', error);
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load variables: ${error.message}`,
        });
        throw error;
      }
    },
    [dispatch]
  );

  // Load locations with filtering
  const loadLocations = useCallback(
    async (filters = {}, table = null) => {
      try {
        dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: true } });

        // Use getMetrics for filtered location data with metrics, or getLocations for basic locations
        const locations =
          filters.configuration && filters.variable
            ? await apiService.getMetrics({ ...filters, table })
            : await apiService.getLocations();

        dispatch({ type: ActionTypes.SET_LOCATIONS, payload: locations });
      } catch (error) {
        console.error('useRetrospectiveDataFetching: Error loading locations:', error);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: false } });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load locations: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  // Load timeseries data
  const loadTimeseries = useCallback(
    async (filters = {}) => {
      try {
        // Clear existing timeseries data first
        dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
        dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });

        const { primary_location_id, configurations, variable, start_date, end_date, duration } =
          filters;

        if (!primary_location_id || !configurations?.length || !variable) {
          throw new Error(
            'Missing required parameters: primary_location_id, configurations, and variable are required'
          );
        }

        // Load primary data (USGS observations)
        // Convert _inst variable names to primary_timeseries canonical form (e.g. streamflow_hourly_inst -> streamflow_none_inst)
        // and include duration filter only for instantaneous (_inst) variables
        const primaryVariable = variable?.endsWith('_inst')
          ? toPrimaryVariableName(variable)
          : variable;
        const primaryFilters = {
          variable: primaryVariable,
          start_date,
          end_date,
          ...(variable?.endsWith('_inst') && duration && { duration }),
        };
        const primaryData = await apiService.getPrimaryTimeseries(
          primary_location_id,
          primaryFilters
        );
        dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });

        // Load secondary data with multi-value configuration filtering
        const secondaryFilters = {
          variable,
          start_date,
          end_date,
          configuration: configurations,
        };

        const secondaryData = await apiService.getSecondaryTimeseries(
          primary_location_id,
          secondaryFilters
        );
        dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
      } catch (error) {
        console.error('Error loading timeseries:', error);
        dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: false } });
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to load timeseries: ${error.message}`,
        });
      }
    },
    [dispatch]
  );

  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await Promise.all([loadConfigurations(), loadVariables()]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables]);

  return {
    loadConfigurations,
    loadVariables,
    loadLocations,
    loadTimeseries,
    initializeData,
  };
};

// Custom hook for filter management
export const useRetrospectiveFilters = () => {
  const { state, dispatch } = useRetrospectiveDashboard();

  const updateMapFilters = useCallback(
    (filters) => {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
    },
    [dispatch]
  );

  const updateTimeseriesFilters = useCallback(
    (filters) => {
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
    (location) => {
      dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
      // Always clear timeseries when location changes (including deselection)
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
    },
    [dispatch]
  );

  return {
    selectedLocation: state.selectedLocation,
    selectLocation,
  };
};
