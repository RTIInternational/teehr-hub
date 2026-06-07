/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';
import { NWMD_DASHBOARD_DEFAULTS, selectDefault } from '../config/dashboardDefaults';

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

// Initial state for nwmd dashboard  
const initialNwmdState = {
  // Data
  locations: { features: [] },
  configurations: [],
  variables: [],
  thresholds: [],
  aggMethods: [],
  leadTimeBins: [],
  tableProperties: {}, // Will contain { "table_name": { metrics: [], group_by: [], description: "" } }
  mapViewportBounds: null,
  
  // Map filters (original structure)
  mapFilters: {
    configuration: null,
    variable: null,
    threshold: null,
    aggMethod: null,
    leadTimeBin: null,
    metricName: 'relative_bias'
  },
  
  // Timeseries filters (nwmd-specific defaults)
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

  // CDF plots
  cdfPlotOrder: ['plot1'],
  cdfPlots: {
    plot1: {
      metricName: 'relative_bias'
    }
  },
  
  // Loading states
  locationsLoading: false,
  timeseriesLoading: false,
  metricsLoading: false,
  tablePropertiesLoading: false,
  configurationsLoading: false,
  variablesLoading: false,
  thresholdsLoading: false,
  aggMethodsLoading: false,
  leadTimeBinsLoading: false,
  
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
  SET_THRESHOLDS: 'SET_THRESHOLDS',
  SET_AGG_METHODS: 'SET_AGG_METHODS',
  SET_LEAD_TIME_BINS: 'SET_LEAD_TIME_BINS',
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

  // CDF plots
  SET_CDF_PLOT_METRIC: 'SET_CDF_PLOT_METRIC',
  
  // Loading states
  SET_LOADING: 'SET_LOADING',
  
  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_MAP_VIEWPORT_BOUNDS: 'SET_MAP_VIEWPORT_BOUNDS',
  
  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR'
};

// Reducer function (same logic as retrospective)
const nwmdDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false
      };
      
    case ActionTypes.SET_CONFIGURATIONS: {
      const configurations = Array.isArray(action.payload) ? action.payload : [];
      const defaultConfig = selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredConfiguration, configurations);
      return {
        ...state,
        configurations,
        configurationsLoading: false,
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
      const defaultVariable = selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredVariable, variables);
      return {
        ...state,
        variables,
        variablesLoading: false,
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

    case ActionTypes.SET_THRESHOLDS: {
      const thresholds = Array.isArray(action.payload) ? action.payload : [];
      const defaultThreshold = selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredThreshold, thresholds);
      return {
        ...state,
        thresholds,
        thresholdsLoading: false,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          threshold: state.mapFilters.threshold || defaultThreshold
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          secondary: {
            ...state.timeseriesFilters.secondary,
            thresholds: state.timeseriesFilters.secondary?.thresholds?.length > 0
              ? state.timeseriesFilters.secondary.thresholds
              : (defaultThreshold ? [defaultThreshold] : [])
          }
        }
      };
    }

    case ActionTypes.SET_AGG_METHODS: {
      const aggMethods = Array.isArray(action.payload) ? action.payload : [];
      const defaultAggMethod = selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredAggMethod, aggMethods);
      return {
        ...state,
        aggMethods,
        aggMethodsLoading: false,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          aggMethod: state.mapFilters.aggMethod || defaultAggMethod
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          secondary: {
            ...state.timeseriesFilters.secondary,
            aggMethods: state.timeseriesFilters.secondary?.aggMethods?.length > 0
              ? state.timeseriesFilters.secondary.aggMethods
              : (defaultAggMethod ? [defaultAggMethod] : [])
          }
        }
      };
    }

    case ActionTypes.SET_LEAD_TIME_BINS: {
      const leadTimeBins = Array.isArray(action.payload) ? action.payload : [];
      const defaultLeadTimeBin = selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredLeadTimeBin, leadTimeBins);
      return {
        ...state,
        leadTimeBins,
        leadTimeBinsLoading: false,
        // Set defaults if first time loading - prefer configured default if available
        mapFilters: {
          ...state.mapFilters,
          leadTimeBin: state.mapFilters.leadTimeBin || defaultLeadTimeBin
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          secondary: {
            ...state.timeseriesFilters.secondary,
            leadTimeBins: state.timeseriesFilters.secondary?.leadTimeBins?.length > 0
              ? state.timeseriesFilters.secondary.leadTimeBins
              : (defaultLeadTimeBin ? [defaultLeadTimeBin] : [])
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
      
    case ActionTypes.UPDATE_MAP_FILTERS: {
      // Keep timeseries defaults in sync with map display filters.
      // This mirrors retrospective behavior where map filter changes reset
      // the default timeseries selections.
      const mapTimeseriesSync = {};
      if (action.payload.configuration !== undefined) {
        mapTimeseriesSync.secondary = {
          ...state.timeseriesFilters.secondary,
          configurations: action.payload.configuration ? [action.payload.configuration] : []
        };
      }
      if (action.payload.variable !== undefined) {
        mapTimeseriesSync.primary = {
          ...state.timeseriesFilters.primary,
          variables: action.payload.variable ? [action.payload.variable] : []
        };
        mapTimeseriesSync.secondary = {
          ...(mapTimeseriesSync.secondary || state.timeseriesFilters.secondary),
          variables: action.payload.variable ? [action.payload.variable] : []
        };
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

    case ActionTypes.SET_CDF_PLOT_METRIC:
      return {
        ...state,
        cdfPlots: {
          ...state.cdfPlots,
          [action.payload.plotId]: {
            ...state.cdfPlots[action.payload.plotId],
            metricName: action.payload.metricName
          }
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
      if ('thresholds' in action.payload) {
        loadingUpdates.thresholdsLoading = action.payload.thresholds;
      }
      if ('aggMethods' in action.payload) {
        loadingUpdates.aggMethodsLoading = action.payload.aggMethods;
      }
      if ('leadTimeBins' in action.payload) {
        loadingUpdates.leadTimeBinsLoading = action.payload.leadTimeBins;
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

    case ActionTypes.SET_MAP_VIEWPORT_BOUNDS:
      return {
        ...state,
        mapViewportBounds: action.payload || null
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
const NwmdDashboardContext = createContext();

// Provider component
export const NwmdDashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(nwmdDashboardReducer, initialNwmdState);
  
  return (
    <NwmdDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </NwmdDashboardContext.Provider>
  );
};

// Hook to use the context
export const useNwmdDashboard = () => {
  const context = useContext(NwmdDashboardContext);
  if (!context) {
    throw new Error('useNwmdDashboard must be used within a NwmdDashboardProvider');
  }
  return context;
};

export default NwmdDashboardContext;