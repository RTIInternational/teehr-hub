/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

const initialFIROState = {
  locations: { features: [] },
  configurations: [],
  variables: [],
  tableProperties: {},
  mapFilters: {
    configuration: null,
    variable: null,
    metricName: 'relative_bias',
  },
  timeseriesFilters: {
    configurations: [],
    variable: null,
    start_date: null,
    end_date: null,
    reference_start_date: null,
    reference_end_date: null,
    duration: null,
  },
  selectedLocation: null,
  timeseriesData: {
    primary: [],
    secondary: [],
  },
  locationMetrics: [],
  eventRankings: [],
  eventHeatmap: [],
  joinedTimeseries: [],
  locationsLoading: false,
  timeseriesLoading: false,
  metricsLoading: false,
  tablePropertiesLoading: false,
  mapLoaded: false,
  error: null,
};

export const ActionTypes = {
  SET_LOCATIONS: 'SET_LOCATIONS',
  SET_CONFIGURATIONS: 'SET_CONFIGURATIONS',
  SET_VARIABLES: 'SET_VARIABLES',
  SET_TABLE_PROPERTIES: 'SET_TABLE_PROPERTIES',
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',
  SELECT_LOCATION: 'SELECT_LOCATION',
  SET_PRIMARY_TIMESERIES: 'SET_PRIMARY_TIMESERIES',
  SET_SECONDARY_TIMESERIES: 'SET_SECONDARY_TIMESERIES',
  CLEAR_TIMESERIES: 'CLEAR_TIMESERIES',
  SET_LOCATION_METRICS: 'SET_LOCATION_METRICS',
  CLEAR_LOCATION_METRICS: 'CLEAR_LOCATION_METRICS',
  SET_EVENT_RANKINGS: 'SET_EVENT_RANKINGS',
  SET_EVENT_HEATMAP: 'SET_EVENT_HEATMAP',
  SET_JOINED_TIMESERIES: 'SET_JOINED_TIMESERIES',
  SET_LOADING: 'SET_LOADING',
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

const firoDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false,
      };

    case ActionTypes.SET_CONFIGURATIONS: {
      const configurations = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        configurations,
        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration || configurations[0] || null,
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          configurations: state.timeseriesFilters.configurations.length > 0
            ? state.timeseriesFilters.configurations
            : (configurations[0] ? [configurations[0]] : []),
        },
      };
    }

    case ActionTypes.SET_VARIABLES: {
      const variables = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        variables,
        mapFilters: {
          ...state.mapFilters,
          variable: state.mapFilters.variable || variables[0] || null,
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          variable: state.timeseriesFilters.variable || variables[0] || null,
        },
      };
    }

    case ActionTypes.SET_TABLE_PROPERTIES:
      return {
        ...state,
        tableProperties: action.payload || {},
        tablePropertiesLoading: false,
      };

    case ActionTypes.UPDATE_MAP_FILTERS: {
      const nextMapFilters = {
        ...state.mapFilters,
        ...action.payload,
      };

      return {
        ...state,
        mapFilters: nextMapFilters,
        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...(action.payload.configuration !== undefined ? {
            configurations: action.payload.configuration ? [action.payload.configuration] : [],
          } : {}),
          ...(action.payload.variable !== undefined ? {
            variable: action.payload.variable || null,
          } : {}),
        },
      };
    }

    case ActionTypes.UPDATE_TIMESERIES_FILTERS:
      return {
        ...state,
        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...action.payload,
        },
      };

    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload,
      };

    case ActionTypes.SET_PRIMARY_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          ...state.timeseriesData,
          primary: action.payload,
        },
      };

    case ActionTypes.SET_SECONDARY_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          ...state.timeseriesData,
          secondary: action.payload,
        },
        timeseriesLoading: false,
      };

    case ActionTypes.CLEAR_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          primary: [],
          secondary: [],
        },
      };

    case ActionTypes.SET_LOCATION_METRICS:
      return {
        ...state,
        locationMetrics: action.payload,
        metricsLoading: false,
      };

    case ActionTypes.SET_EVENT_RANKINGS:
      return {
        ...state,
        eventRankings: action.payload || [],
      };

    case ActionTypes.SET_EVENT_HEATMAP:
      return {
        ...state,
        eventHeatmap: action.payload || [],
      };

    case ActionTypes.SET_JOINED_TIMESERIES:
      return {
        ...state,
        joinedTimeseries: action.payload || [],
      };

    case ActionTypes.CLEAR_LOCATION_METRICS:
      return {
        ...state,
        locationMetrics: [],
        metricsLoading: false,
      };

    case ActionTypes.SET_LOADING: {
      const loadingUpdates = {};
      if ('locations' in action.payload) loadingUpdates.locationsLoading = action.payload.locations;
      if ('timeseries' in action.payload) loadingUpdates.timeseriesLoading = action.payload.timeseries;
      if ('metricsLoading' in action.payload) loadingUpdates.metricsLoading = action.payload.metricsLoading;
      if ('tablePropertiesLoading' in action.payload) loadingUpdates.tablePropertiesLoading = action.payload.tablePropertiesLoading;
      if ('configurations' in action.payload) loadingUpdates.configurationsLoading = action.payload.configurations;
      if ('variables' in action.payload) loadingUpdates.variablesLoading = action.payload.variables;
      return {
        ...state,
        ...loadingUpdates,
      };
    }

    case ActionTypes.SET_MAP_LOADED:
      return {
        ...state,
        mapLoaded: action.payload,
      };

    case ActionTypes.SET_ERROR:
      return {
        ...state,
        error: action.payload,
      };

    case ActionTypes.CLEAR_ERROR:
      return {
        ...state,
        error: null,
      };

    default:
      return state;
  }
};

const FIRODashboardContext = createContext();

export const FIRODashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(firoDashboardReducer, initialFIROState);

  return (
    <FIRODashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </FIRODashboardContext.Provider>
  );
};

export const useFIRODashboard = () => {
  const context = useContext(FIRODashboardContext);
  if (!context) {
    throw new Error('useFIRODashboard must be used within a FIRODashboardProvider');
  }
  return context;
};

export default FIRODashboardContext;
