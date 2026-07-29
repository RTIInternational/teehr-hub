import { useCallback } from 'react';
import { useFIRODashboard, ActionTypes } from '../context/FIRODashboardContext.jsx';
import { apiService } from '../services/api';
import { extractTableProperties } from '../utils/ogcTransformers';

const FIRO_TABLES = ['locations_metrics', 'event_rankings', 'event_heatmap'];

export const useFIRODataFetching = () => {
  const { dispatch } = useFIRODashboard();

  const loadConfigurations = useCallback(async (table = 'locations_metrics') => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { configurations: true } });
      const configurations = await apiService.getConfigurations(table);
      dispatch({ type: ActionTypes.SET_CONFIGURATIONS, payload: configurations });
      return configurations;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load configurations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  const loadVariables = useCallback(async (table = 'locations_metrics') => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { variables: true } });
      const variables = await apiService.getVariables(table);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: variables });
      return variables;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  const loadTableProperties = useCallback(async (tables = FIRO_TABLES) => {
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
      return tableProperties;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load table properties: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  const loadLocations = useCallback(async (filters = {}, table = 'locations_metrics') => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: true } });
      const locations = filters.configuration && filters.variable
        ? await apiService.getMetrics({ ...filters, table })
        : await apiService.getLocations();
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: locations });
      return locations;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { locations: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load locations: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  const loadTimeseries = useCallback(async (filters = {}) => {
    try {
      dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
      dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: true } });

      const {
        primary_location_id,
        configurations,
        variable,
        start_date,
        end_date,
        reference_start_date,
        reference_end_date,
      } = filters;

      if (!primary_location_id || !configurations?.length || !variable) {
        throw new Error('Missing required parameters: primary_location_id, configurations, and variable are required');
      }

      const [primaryData, secondaryData] = await Promise.all([
        apiService.getPrimaryTimeseries(primary_location_id, {
          variable,
          start_date,
          end_date,
        }),
        apiService.getSecondaryTimeseries(primary_location_id, {
          variable,
          start_date,
          end_date,
          reference_start_date,
          reference_end_date,
          configuration: configurations,
        }),
      ]);

      dispatch({ type: ActionTypes.SET_PRIMARY_TIMESERIES, payload: primaryData });
      dispatch({ type: ActionTypes.SET_SECONDARY_TIMESERIES, payload: secondaryData });
      return { primaryData, secondaryData };
    } catch (error) {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { timeseries: false } });
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timeseries: ${error.message}` });
      throw error;
    }
  }, [dispatch]);

  const loadLocationMetrics = useCallback(async (primaryLocationId, table = 'locations_metrics') => {
    try {
      dispatch({ type: ActionTypes.SET_LOADING, payload: { metricsLoading: true } });
      const metricsData = await apiService.getMetrics({ primary_location_id: primaryLocationId, table });
      const locationData = metricsData?.features?.map((feature) => feature.properties || {}) || [];
      dispatch({ type: ActionTypes.SET_LOCATION_METRICS, payload: locationData });
      return locationData;
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load location metrics: ${error.message}` });
      dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
      throw error;
    }
  }, [dispatch]);

  const loadFIROSupplementaryData = useCallback(async (primaryLocationId, filters = {}) => {
    try {
      const [eventRankingsData, eventHeatmapData, joinedTimeseriesData] = await Promise.all([
        apiService.getMetrics({ primary_location_id: primaryLocationId, table: 'event_rankings', ...filters }),
        apiService.getMetrics({ primary_location_id: primaryLocationId, table: 'event_heatmap', ...filters }),
        apiService.getMetrics({ primary_location_id: primaryLocationId, table: 'joined_timeseries', ...filters }),
      ]);

      dispatch({ type: ActionTypes.SET_EVENT_RANKINGS, payload: eventRankingsData?.features?.map((feature) => feature.properties || {}) || [] });
      dispatch({ type: ActionTypes.SET_EVENT_HEATMAP, payload: eventHeatmapData?.features?.map((feature) => feature.properties || {}) || [] });
      dispatch({ type: ActionTypes.SET_JOINED_TIMESERIES, payload: joinedTimeseriesData?.features?.map((feature) => feature.properties || {}) || [] });
    } catch (error) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load FIRO supplementary data: ${error.message}` });
    }
  }, [dispatch]);

  const initializeData = useCallback(async () => {
    try {
      await Promise.all([
        loadConfigurations(),
        loadVariables(),
        loadTableProperties(),
      ]);
    } catch (error) {
      console.error('Failed to initialize FIRO data:', error);
      throw error;
    }
  }, [loadConfigurations, loadVariables, loadTableProperties]);

  return {
    loadConfigurations,
    loadVariables,
    loadTableProperties,
    loadLocations,
    loadTimeseries,
    loadLocationMetrics,
    loadFIROSupplementaryData,
    initializeData,
  };
};

export const useFIROFilters = () => {
  const { state, dispatch } = useFIRODashboard();

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
    updateTimeseriesFilters,
  };
};

export const useFIROLocationSelection = () => {
  const { state, dispatch } = useFIRODashboard();

  const selectLocation = useCallback((location) => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: location });
    dispatch({ type: ActionTypes.CLEAR_TIMESERIES });
    dispatch({ type: ActionTypes.CLEAR_LOCATION_METRICS });
  }, [dispatch]);

  return {
    selectedLocation: state.selectedLocation,
    selectLocation,
  };
};
