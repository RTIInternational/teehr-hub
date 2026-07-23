import { useCallback } from 'react';
import { useForecastDashboard, ActionTypes } from '../context/ForecastDashboardContext.jsx';
import { apiService } from '../services/api';
import { extractTableProperties } from '../utils/ogcTransformers';
import { groupVariablesByDuration, toPrimaryVariableName, ISO_TO_DURATION_NAME, expandPrimaryVariables } from '../utils/durationUtils';

// Custom hooks for forecast dashboard data fetching
export const useForecastDataFetching = () => {
  const { dispatch } = useForecastDashboard();
  
  // Load configurations (distinct values from database)
  const loadConfigurations = useCallback(async (table) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
      // Use the new distinct values endpoint
      const configurations = await apiService.getConfigurations(table);
      dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load variables (distinct values from database)
  const loadVariables = useCallback(async (table) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
      // Use the new distinct values endpoint
      const variables = await apiService.getVariables(table);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load primary_timeseries variable names and expand them using DURATION_NAME_TO_ISO
  const loadPrimaryVariables = useCallback(async () => {
    try {
      const rawVariables = await apiService.getVariables('primary_timeseries');
      dispatch({ type: ActionTypes.SET_PRIMARY_VARIABLES, payload: expandPrimaryVariables(rawVariables) });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load primary variables: ${error.message}` });
    }
  }, [dispatch]);

  // Load table properties (batch) from queryables
  const loadTableProperties = useCallback(async (tables) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { tablePropertiesLoading: true } });
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
      
      dispatch({ type: ActionTypes.SET_TABLE_PROPERTIES, payload: tableProperties });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load table properties: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load locations with filtering
  const loadLocations = useCallback(async (filters = {}, table = null) => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: true } });
      
      // Use getMetrics for filtered location data with metrics, or getLocations for basic locations
      const locations = filters.configuration && filters.variable 
        ? await apiService.getMetrics({ ...filters, table })
        : await apiService.getLocations();
      
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: locations });
    } catch (error) {
      console.error('useForecastDataFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load timeseries data
  const loadTimeseries = useCallback(async (filters = {}) => {
    try {
      // Clear existing timeseries data first
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
      dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });
      
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
        reference_end_date
      } = filters;

      const legacyVariables = Array.isArray(variables)
        ? variables
        : (variable ? [variable] : []);

      const primaryFilters = {
        variables: primary.variables ?? legacyVariables,
        start_date: primary.start_date ?? start_date,
        end_date: primary.end_date ?? end_date
      };

      const secondaryFilters = {
        configurations: secondary.configurations ?? configurations,
        variables: secondary.variables ?? legacyVariables,
        reference_start_date: secondary.reference_start_date ?? reference_start_date,
        reference_end_date: secondary.reference_end_date ?? reference_end_date
      };
      
      if (
        !primary_location_id
        || !secondaryFilters.configurations?.length
        || !primaryFilters.variables?.length
        || !secondaryFilters.variables?.length
      ) {
        throw new Error('Missing required parameters: primary_location_id, primary.variables, secondary.variables, and secondary.configurations are required');
      }

      // Group variables by duration and issue one call per unique duration group.
      // Variables with a non-'inst' statistic (e.g. _mean) have duration=null and
      // are passed through without a duration filter.
      const primaryGroups = groupVariablesByDuration(primaryFilters.variables);
      const secondaryGroups = groupVariablesByDuration(secondaryFilters.variables);

      const [primaryData, secondaryData] = await Promise.all([
        Promise.all(
          Array.from(primaryGroups.entries()).map(([duration, variables]) =>
            apiService.getPrimaryTimeseries(primary_location_id, {
              variable: variables.map(toPrimaryVariableName),
              start_date: primaryFilters.start_date,
              end_date: primaryFilters.end_date,
              ...(duration && { duration })
            }).then(results => results.map(series => ({
              ...series,
              duration_token: duration ? ISO_TO_DURATION_NAME[duration] : null
            })))
          )
        ).then(results => results.flat()),
        Promise.all(
          Array.from(secondaryGroups.entries()).map(([duration, variables]) =>
            apiService.getSecondaryTimeseries(primary_location_id, {
              variable: variables,
              reference_start_date: secondaryFilters.reference_start_date,
              reference_end_date: secondaryFilters.reference_end_date,
              configuration: secondaryFilters.configurations,
              ...(duration && { duration })
            })
          )
        ).then(results => results.flat())
      ]);

      dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });
      dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
      
    } catch (error) {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timeseries: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load location-specific metrics
  const loadLocationMetrics = useCallback(async (primaryLocationId, table) => {
    try {
      console.log('Loading metrics for location:', primaryLocationId, 'table:', table);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { metricsLoading: true } });
      
      const metricsData = await apiService.getMetrics({
        primary_location_id: primaryLocationId,
        table: table 
      });
      
      console.log('Location metrics GeoJSON loaded:', metricsData);
      
      // Extract raw properties from GeoJSON features for pivoting
      let locationData = [];
      if (metricsData?.features && metricsData.features.length > 0) {
        // Convert each feature to a row of data
        locationData = metricsData.features.map(feature => {
          return feature.properties || {};
        });
      }
      
      console.log('Raw location data for pivoting:', locationData);
      dispatch({ type: ActionTypes.SET_LOCATION_METRICS, payload: locationData });
      return locationData;
    } catch (error) {
      console.error('Error loading location metrics:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load location metrics: ${error.message}` });
      dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
      throw error;
    }
  }, [dispatch]);
  
  // Initialize all data
  const initializeData = useCallback(async () => {
    try {
      await Promise.all([
        loadConfigurations(),
        loadVariables(),
        loadTableProperties()
      ]);
    } catch (error) {
      console.error('Failed to initialize data:', error);
    }
  }, [loadConfigurations, loadVariables, loadTableProperties]);
  
  return {
    loadConfigurations,
    loadVariables,
    loadPrimaryVariables,
    loadTableProperties,
    loadLocations,
    loadTimeseries,
    loadLocationMetrics,
    initializeData
  };
};

// Custom hook for filter management
export const useForecastFilters = () => {
  const { state, dispatch } = useForecastDashboard();
  
  const updateMapFilters = useCallback((filters) => {
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: filters });
  }, [dispatch]);
  
  const updateTimeseriesFilters = useCallback((filters) => {
    dispatch({ type: ActionTypes.UPDATE_TIMESERIES_FILTERS, payload: filters });
  }, [dispatch]);
  
  return {
    mapFilters: state.mapFilters,
    timeseriesFilters: state.timeseriesFilters,
    updateMapFilters,
    updateTimeseriesFilters
  };
};

// Custom hook for location selection
export const useForecastLocationSelection = () => {
  const { state, dispatch } = useForecastDashboard();
  
  const selectLocation = useCallback((location) => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    // Always clear timeseries when location changes (including deselection)
    dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
    // Clear metrics when location changes
    dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
  }, [dispatch]);
  
  return {
    selectedLocation: state.selectedLocation,
    selectLocation
  };
};