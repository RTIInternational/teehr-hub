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
  configurations: [],
  variables: [],
  primaryVariables: [],

  // Map filters (original structure)
  mapFilters: {
    configuration: null,
    variable: null,
    metricName: 'relative_bias',
  },

  // Timeseries filters (forecast-specific defaults)
  timeseriesFilters: {
    primary: {
      variables: [FORECAST_DASHBOARD_DEFAULTS.preferredObservationsVariable],
      start_date: getTenDaysAgo(),
      end_date: getToday(),
      duration: FORECAST_DASHBOARD_DEFAULTS.preferredObservationsDuration,
    },
    secondary: {
      configurations: [], // Array for multi-select
      variables: [],
      reference_start_date: getTenDaysAgo(),
      reference_end_date: getToday(),
    },
  },

  // Selected location
  selectedLocation: null,

  // Map state
  mapLoaded: false,

  // Error state
  error: null,
};

// Action types (same as retrospective)
export const ActionTypes = {
  // Data loading
  SET_CONFIGURATIONS: 'SET_CONFIGURATIONS',
  SET_VARIABLES: 'SET_VARIABLES',
  SET_PRIMARY_VARIABLES: 'SET_PRIMARY_VARIABLES',

  // Filter updates
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',

  // Location selection
  SELECT_LOCATION: 'SELECT_LOCATION',

  // Loading states
  SET_LOADING: 'SET_LOADING',

  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',

  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer function (same logic as retrospective)
const forecastDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_CONFIGURATIONS: {
      const configurations = Array.isArray(action.payload) ? action.payload : [];
      const defaultConfig = selectDefault(
        FORECAST_DASHBOARD_DEFAULTS.preferredConfiguration,
        configurations
      );
      return {
        ...state,
        configurations,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration || defaultConfig,
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          secondary: {
            ...state.timeseriesFilters.secondary,
            configurations:
              state.timeseriesFilters.secondary?.configurations?.length > 0
                ? state.timeseriesFilters.secondary.configurations
                : defaultConfig
                  ? [defaultConfig]
                  : [],
          },
        },
      };
    }

    case ActionTypes.SET_VARIABLES: {
      const variables = Array.isArray(action.payload) ? action.payload : [];
      const defaultVariable = selectDefault(
        FORECAST_DASHBOARD_DEFAULTS.preferredVariable,
        variables
      );
      return {
        ...state,
        variables,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          variable: state.mapFilters.variable || defaultVariable,
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          // primary.variables is intentionally NOT set here — it is only populated
          // from SET_PRIMARY_VARIABLES (Observations dropdown) to avoid passing
          // fcst_metrics variable names (e.g. streamflow_6hr_inst) to duration parsing.
          secondary: {
            ...state.timeseriesFilters.secondary,
            variables:
              state.timeseriesFilters.secondary?.variables?.length > 0
                ? state.timeseriesFilters.secondary.variables
                : defaultVariable
                  ? [defaultVariable]
                  : [],
          },
        },
      };
    }

    case ActionTypes.SET_PRIMARY_VARIABLES: {
      const primaryVariables = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        primaryVariables,
        // Initialize primary.variables to the first available option if not yet set.
        // This is the only place primary.variables is ever auto-populated.
        timeseriesFilters: {
          ...state.timeseriesFilters,
          primary: {
            ...state.timeseriesFilters.primary,
            variables:
              state.timeseriesFilters.primary?.variables?.length > 0
                ? state.timeseriesFilters.primary.variables
                : primaryVariables.length > 0
                  ? [primaryVariables[0]]
                  : [],
          },
        },
      };
    }

    case ActionTypes.UPDATE_MAP_FILTERS: {
      // the default timeseries selections. // This mirrors retrospective behavior where map filter changes reset // Keep timeseries defaults in sync with map display filters.
      const mapTimeseriesSync = {};
      if (action.payload.configuration !== undefined) {
        mapTimeseriesSync.secondary = {
          ...state.timeseriesFilters.secondary,
          configurations: action.payload.configuration ? [action.payload.configuration] : [],
        };
      }
      if (action.payload.variable !== undefined) {
        // primary.variables is NOT synced from the map variable — it is controlled
        // exclusively by the Observations dropdown (state.primaryVariables).
        mapTimeseriesSync.secondary = {
          ...(mapTimeseriesSync.secondary || state.timeseriesFilters.secondary),
          variables: action.payload.variable ? [action.payload.variable] : [],
        };
      }
      return {
        ...state,
        mapFilters: {
          ...state.mapFilters,
          ...action.payload,
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...mapTimeseriesSync,
        },
      };
    }

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
            ...(primary || {}),
          },
          secondary: {
            ...state.timeseriesFilters.secondary,
            ...legacySecondary,
            ...(secondary || {}),
          },
        },
      };
    }

    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload,
      };

    case ActionTypes.SET_LOADING: {
      // Map shorthand keys to actual state property names
      const loadingUpdates = {};
      if ('configurations' in action.payload) {
        loadingUpdates.configurationsLoading = action.payload.configurations;
      }
      if ('variables' in action.payload) {
        loadingUpdates.variablesLoading = action.payload.variables;
      }
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
