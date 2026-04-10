/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';
import { RETROSPECTIVE_DASHBOARD_DEFAULTS, selectDefault } from '../config/dashboardDefaults';

// Static date defaults for retrospective - uses 2020 data
const DEFAULT_START_DATE = RETROSPECTIVE_DASHBOARD_DEFAULTS.defaultStartDate;
const DEFAULT_END_DATE = RETROSPECTIVE_DASHBOARD_DEFAULTS.defaultEndDate;

// Initial state for retrospective dashboard
const initialRetrospectiveState = {
  // Data
  locations: { features: [] },
  configurations: [],
  variables: [],
  tableProperties: {}, // Will contain { "table_name": { metrics: [], group_by: [], description: "" } }
  
  // Map filters (original structure)
  mapFilters: {
    configuration: null,
    variable: null,
    metricName: 'relative_bias'
  },
  
  // Timeseries filters (retrospective-specific defaults - year 2020)
  timeseriesFilters: {
    configurations: [], // Array for multi-select
    variable: null,
    start_date: DEFAULT_START_DATE,
    end_date: DEFAULT_END_DATE,
    reference_start_date: null,
    reference_end_date: null
  },
  
  // Selected location
  selectedLocation: null,
  
  // Timeseries data (structured as expected by components)
  timeseriesData: {
    primary: [],
    secondary: []
  },
  
  // Metrics table data
  locationMetrics: [],
  
  // Loading states
  locationsLoading: false,
  timeseriesLoading: false,
  metricsLoading: false,
  tablePropertiesLoading: false,
  
  // Map state
  mapLoaded: false,
  
  // Error state
  error: null
};

// Action types (same as original)
export const ActionTypes = {
  // Data loading
  SET_LOCATIONS: 'SET_LOCATIONS',
  SET_CONFIGURATIONS: 'SET_CONFIGURATIONS',
  SET_VARIABLES: 'SET_VARIABLES',
  SET_TABLE_PROPERTIES: 'SET_TABLE_PROPERTIES',
  
  // Filter updates
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',
  
  // Location selection
  SELECT_LOCATION: 'SELECT_LOCATION',
  
  // Timeseries data
  SET_PRIMARY_TIMESERIES: 'SET_PRIMARY_TIMESERIES',
  SET_SECONDARY_TIMESERIES: 'SET_SECONDARY_TIMESERIES',
  CLEAR_TIMESERIES: 'CLEAR_TIMESERIES',
  
  // Location metrics
  SET_LOCATION_METRICS: 'SET_LOCATION_METRICS',
  CLEAR_LOCATION_METRICS: 'CLEAR_LOCATION_METRICS',
  
  // Loading states
  SET_LOADING: 'SET_LOADING',
  
  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  
  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR'
};

// Reducer function (same logic as original)
const retrospectiveDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false
      };
      
    case ActionTypes.SET_CONFIGURATIONS:
      const configurations = Array.isArray(action.payload) ? action.payload : [];
      const defaultConfig = selectDefault(RETROSPECTIVE_DASHBOARD_DEFAULTS.preferredConfiguration, configurations);
      return {
        ...state,
        configurations,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration || defaultConfig
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          configurations: state.timeseriesFilters.configurations?.length > 0 
            ? state.timeseriesFilters.configurations 
            : (defaultConfig ? [defaultConfig] : [])
        }
      };
      
    case ActionTypes.SET_VARIABLES:
      const variables = Array.isArray(action.payload) ? action.payload : [];
      const defaultVariable = selectDefault(RETROSPECTIVE_DASHBOARD_DEFAULTS.preferredVariable, variables);
      return {
        ...state,
        variables,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          variable: state.mapFilters.variable || defaultVariable
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          variable: state.timeseriesFilters.variable || defaultVariable
        }
      };
      
    case ActionTypes.SET_TABLE_PROPERTIES:
      const tableProperties = action.payload || {};
      return {
        ...state,
        tableProperties,
        tablePropertiesLoading: false
      };
      
    case ActionTypes.UPDATE_MAP_FILTERS:
      // Also sync configuration and variable to timeseries filters
      const mapTimeseriesSync = {};
      if (action.payload.configuration !== undefined) {
        // Sync map configuration to timeseries configurations array
        mapTimeseriesSync.configurations = action.payload.configuration ? [action.payload.configuration] : [];
      }
      if (action.payload.variable !== undefined) {
        mapTimeseriesSync.variable = action.payload.variable;
      }
      return {
        ...state,
        mapFilters: {
          ...state.mapFilters,
          ...action.payload
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...mapTimeseriesSync
        }
      };
      
    case ActionTypes.UPDATE_TIMESERIES_FILTERS:
      return {
        ...state,
        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...action.payload
        }
      };
      
    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload
      };
      
    case ActionTypes.SET_PRIMARY_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          ...state.timeseriesData,
          primary: action.payload
        }
      };
      
    case ActionTypes.SET_SECONDARY_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          ...state.timeseriesData,
          secondary: action.payload
        },
        timeseriesLoading: false
      };
      
    case ActionTypes.CLEAR_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          primary: [],
          secondary: []
        }
      };
      
    case ActionTypes.SET_LOADING:
      // Map shorthand keys to actual state property names
      const loadingUpdates = {};
      if ('locations' in action.payload) {
        loadingUpdates.locationsLoading = action.payload.locations;
      }
      if ('timeseries' in action.payload) {
        loadingUpdates.timeseriesLoading = action.payload.timeseries;
      }
      if ('metricsLoading' in action.payload) {
        loadingUpdates.metricsLoading = action.payload.metricsLoading;
      }
      if ('tablePropertiesLoading' in action.payload) {
        loadingUpdates.tablePropertiesLoading = action.payload.tablePropertiesLoading;
      }
      if ('configurations' in action.payload) {
        loadingUpdates.configurationsLoading = action.payload.configurations;
      }
      if ('variables' in action.payload) {
        loadingUpdates.variablesLoading = action.payload.variables;
      }
      return {
        ...state,
        ...loadingUpdates
      };
      
    case ActionTypes.SET_MAP_LOADED:
      return {
        ...state,
        mapLoaded: action.payload
      };
      
    case ActionTypes.SET_ERROR:
      return {
        ...state,
        error: action.payload
      };
      
    case ActionTypes.CLEAR_ERROR:
      return {
        ...state,
        error: null
      };
      
    case ActionTypes.SET_LOCATION_METRICS:
      return {
        ...state,
        locationMetrics: action.payload,
        metricsLoading: false
      };
      
    case ActionTypes.CLEAR_LOCATION_METRICS:
      return {
        ...state,
        locationMetrics: [],
        metricsLoading: false
      };
      
    default:
      return state;
  }
};

// Create context
const RetrospectiveDashboardContext = createContext();

// Provider component
export const RetrospectiveDashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(retrospectiveDashboardReducer, initialRetrospectiveState);
  
  return (
    <RetrospectiveDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </RetrospectiveDashboardContext.Provider>
  );
};

// Hook to use the context
export const useRetrospectiveDashboard = () => {
  const context = useContext(RetrospectiveDashboardContext);
  if (!context) {
    throw new Error('useRetrospectiveDashboard must be used within a RetrospectiveDashboardProvider');
  }
  return context;
};

export default RetrospectiveDashboardContext;