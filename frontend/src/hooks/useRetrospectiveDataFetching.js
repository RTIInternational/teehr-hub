import { useCallback } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../context/RetrospectiveDashboardContext.jsx';
import { apiService } from '../services/api';
import { extractTableProperties, coverageJsonToPlotlyFormat } from '../utils/ogcTransformers';

// Custom hooks for retrospective dashboard data fetching
export const useRetrospectiveDataFetching = () => {
  const { dispatch } = useRetrospectiveDashboard();
  
  // Load configurations (distinct values from database)
  const loadConfigurations = useCallback(async (table) => {
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
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);
  
  // Load variables (distinct values from database)
  const loadVariables = useCallback(async (table) => {
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
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${error.message}` });
      throw error;
    }
  }, [dispatch]);
  
  // Load table properties (batch) from queryables
  const loadTableProperties = useCallback(async (tables) => {
    try {
      console.log('Loading table properties for tables:', tables);
      dispatch({ type: ActionTypes.SET_LOADING, payload: { tablePropertiesLoading: true } });
      const tableArray = Array.isArray(tables) ? tables : [tables];
      
      // Fetch queryables for each table and transform to table properties
      const results = await Promise.all(
        tableArray.map(async (table) => {
          const queryables = await apiService.getQueryables(table);
          return { table, properties: extractTableProperties(queryables) };
        })
      );
      
      // Convert to object keyed by table name
      const tableProperties = results.reduce((acc, { table, properties }) => {
        acc[table] = properties;
        return acc;
      }, {});
      
      console.log('Table properties loaded:', tableProperties);
      dispatch({ type: ActionTypes.SET_TABLE_PROPERTIES, payload: tableProperties });
      return tableProperties;
    } catch (error) {
      console.error('Error loading table properties:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load table properties: ${error.message}` });
      throw error;
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
      console.error('useRetrospectiveDataFetching: Error loading locations:', error);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
    }
  }, [dispatch]);
  
  // Load timeseries data
  const loadTimeseries = useCallback(async (filters = {}) => {
      try {
        // Clear existing timeseries data first
        dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
        dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });
        
        const { primary_location_id, configuration, variable, start_date, end_date } = filters;
        
        if (!primary_location_id || !configuration || !variable) {
          throw new Error('Missing required parameters: primary_location_id, configuration, and variable are required');
        }
  
        // Load primary data (USGS observations) - does NOT need configuration
        // Primary timeseries = observed USGS data
        const primaryFilters = {
          variable,
          start_date,
          end_date
        };
        // API returns CoverageJSON - transform to PlotlyChart format
        const primaryCoverage = await apiService.getPrimaryTimeseries(primary_location_id, primaryFilters);
        const primaryData = coverageJsonToPlotlyFormat(primaryCoverage);
        dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });
  
        // Load secondary data (NWM retrospective simulation) - NEEDS configuration
        // Secondary timeseries = simulated data (no reference_time for retrospective)
        const secondaryFilters = {
          configuration,
          variable,
          start_date,
          end_date
        };
        // API returns CoverageJSON - transform to PlotlyChart format
        const secondaryCoverage = await apiService.getSecondaryTimeseries(primary_location_id, secondaryFilters);
        const secondaryData = coverageJsonToPlotlyFormat(secondaryCoverage);
        dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
        
      } catch (error) {
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
    loadTableProperties,
    loadLocations,
    loadTimeseries,
    loadLocationMetrics,
    initializeData
  };
};

// Custom hook for filter management
export const useRetrospectiveFilters = () => {
  const { state, dispatch } = useRetrospectiveDashboard();
  
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
export const useRetrospectiveLocationSelection = () => {
  const { state, dispatch } = useRetrospectiveDashboard();
  
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