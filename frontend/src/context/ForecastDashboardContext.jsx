/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';
import { FORECAST_DASHBOARD_DEFAULTS, selectDefault } from '../config/dashboardDefaults';

// Dynamic date helpers - returns dates for 10 days ago through today
const getTenDaysAgo = () => {
  const date = new Date();
  date.setDate(date.getDate() - 10);
  return date.toISOString().slice(0, 16); // Format: YYYY-MM-DDTHH:MM
};

const getToday = () => {
  const date = new Date();
  return date.toISOString().slice(0, 16); // Format: YYYY-MM-DDTHH:MM
};

// Initial state for forecast dashboard  
const initialForecastState = {
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
  
  // Timeseries filters (forecast-specific defaults)
  timeseriesFilters: {
    primary: {
      variables: [],
      start_date: getTenDaysAgo(),
      end_date: getToday()
    },
    secondary: {
      configurations: [], // Array for multi-select
      variables: [],
      reference_start_date: getTenDaysAgo(),
      reference_end_date: getToday()
    }
  },
  
  // Selected location
  selectedLocation: null,
  
  // Timeseries data (structured as expected by components)
  timeseriesData: {
    primary: [],
    secondary: []
  },
  
  // Location metrics
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

// Action types (same as retrospective)
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

// Reducer function (same logic as retrospective)
const forecastDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false
      };
      
    case ActionTypes.SET_CONFIGURATIONS: {
      const configurations = Array.isArray(action.payload) ? action.payload : [];
      const defaultConfig = selectDefault(FORECAST_DASHBOARD_DEFAULTS.preferredConfiguration, configurations);
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
          secondary: {
            ...state.timeseriesFilters.secondary,
            configurations: state.timeseriesFilters.secondary?.configurations?.length > 0
              ? state.timeseriesFilters.secondary.configurations
              : (defaultConfig ? [defaultConfig] : [])
          }
        }
      };
    }
      
    case ActionTypes.SET_VARIABLES: {
      const variables = Array.isArray(action.payload) ? action.payload : [];
      const defaultVariable = selectDefault(FORECAST_DASHBOARD_DEFAULTS.preferredVariable, variables);
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
          primary: {
            ...state.timeseriesFilters.primary,
            variables: state.timeseriesFilters.primary?.variables?.length > 0
              ? state.timeseriesFilters.primary.variables
              : (defaultVariable ? [defaultVariable] : [])
          },
          secondary: {
            ...state.timeseriesFilters.secondary,
            variables: state.timeseriesFilters.secondary?.variables?.length > 0
              ? state.timeseriesFilters.secondary.variables
              : (defaultVariable ? [defaultVariable] : [])
          }
        }
      };
    }
      
    case ActionTypes.SET_TABLE_PROPERTIES: {
      const tableProperties = action.payload || {};
      return {
        ...state,
        tableProperties,
        tablePropertiesLoading: false
      };
    }
      
    case ActionTypes.UPDATE_MAP_FILTERS:
      return {
        ...state,
        mapFilters: {
          ...state.mapFilters,
          ...action.payload
        }
      };
      
    case ActionTypes.UPDATE_TIMESERIES_FILTERS: {
      // Support both nested ({ primary, secondary }) and legacy flat payloads.
      const { primary, secondary, ...legacy } = action.payload || {};
      const legacyPrimary = {};
      const legacySecondary = {};

      if (legacy.variable !== undefined) {
        legacyPrimary.variables = legacy.variable ? [legacy.variable] : [];
        legacySecondary.variables = legacy.variable ? [legacy.variable] : [];
      }
      if (legacy.variables !== undefined) {
        legacyPrimary.variables = legacy.variables;
        legacySecondary.variables = legacy.variables;
      }
      if (legacy.start_date !== undefined) {
        legacyPrimary.start_date = legacy.start_date;
        legacySecondary.start_date = legacy.start_date;
      }
      if (legacy.end_date !== undefined) {
        legacyPrimary.end_date = legacy.end_date;
        legacySecondary.end_date = legacy.end_date;
      }
      if (legacy.configurations !== undefined) {
        legacySecondary.configurations = legacy.configurations;
      }
      if (legacy.reference_start_date !== undefined) {
        legacySecondary.reference_start_date = legacy.reference_start_date;
      }
      if (legacy.reference_end_date !== undefined) {
        legacySecondary.reference_end_date = legacy.reference_end_date;
      }

      return {
        ...state,
        timeseriesFilters: {
          ...state.timeseriesFilters,
          primary: {
            ...state.timeseriesFilters.primary,
            ...legacyPrimary,
            ...(primary || {})
          },
          secondary: {
            ...state.timeseriesFilters.secondary,
            ...legacySecondary,
            ...(secondary || {})
          }
        }
      };
    }
      
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
      
    case ActionTypes.SET_LOADING: {
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
    }
      
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
const ForecastDashboardContext = createContext();

// Provider component
export const ForecastDashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(forecastDashboardReducer, initialForecastState);
  
  return (
    <ForecastDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </ForecastDashboardContext.Provider>
  );
};

// Hook to use the context
export const useForecastDashboard = () => {
  const context = useContext(ForecastDashboardContext);
  if (!context) {
    throw new Error('useForecastDashboard must be used within a ForecastDashboardProvider');
  }
  return context;
};

export default ForecastDashboardContext;