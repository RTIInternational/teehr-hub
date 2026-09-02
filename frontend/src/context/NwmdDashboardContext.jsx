/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

import { NWMD_DASHBOARD_DEFAULTS } from '../config/dashboardDefaults';
import { getQuarterDateRange } from '../shared/utils/formatters';

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

const syncTimeseriesFiltersForQuarter = (timeseriesFilters, quarter) => {
  const quarterRange = getQuarterDateRange(quarter);
  if (!quarterRange) return {};

  return {
    primary: {
      ...timeseriesFilters.primary,
      start_date: quarterRange.start_date,
      end_date: quarterRange.end_date,
    },
    secondary: {
      ...timeseriesFilters.secondary,
      reference_start_date: quarterRange.start_date,
      reference_end_date: quarterRange.end_date,
    },
  };
};

// Initial state for nwmd dashboard
const initialNwmdState = {
  // Data
  locations: { features: [] },
  tableProperties: {}, // Will contain { "table_name": { metrics: [], group_by: [], description: "" } }
  mapViewportBounds: undefined,

  // Map filters (original structure)
  mapFilters: {
    quarter: undefined,
    configuration: undefined,
    variable: undefined,
    threshold: undefined,
    aggMethod: undefined,
    leadTimeBin: undefined,
    altHypothesis95: undefined,
    metricName: 'relative_bias',
  },

  // Timeseries filters (nwmd-specific defaults)
  timeseriesFilters: {
    primary: {
      variables: [NWMD_DASHBOARD_DEFAULTS.preferredObservationsVariable],
      start_date: getTenDaysAgo(),
      end_date: getToday(),
      duration: NWMD_DASHBOARD_DEFAULTS.preferredObservationsDuration,
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

  // Timeseries data (structured as expected by components)
  timeseriesData: {
    primary: [],
    secondary: [],
  },

  // Lead-time bin metrics for selected location plot
  leadTimeBinMetrics: [],

  // Location metadata
  metadata: undefined,

  // CDF plots
  cdfPlotOrder: ['Metric 1', 'Metric 2', 'Metric 3', 'Metric 4'],
  cdfPlots: {
    'Metric 1': {
      metricName: 'kling_gupta_efficiency',
    },
    'Metric 2': {
      metricName: 'nash_sutcliffe_efficiency',
    },
    'Metric 3': {
      metricName: 'relative_mean',
    },
    'Metric 4': {
      metricName: 'relative_standard_deviation',
    },
  },

  // Loading states
  locationsLoading: false,
  timeseriesLoading: false,
  metadataLoading: false,
  tablePropertiesLoading: false,
  leadTimeBinMetricsLoading: false,

  // Map state
  mapLoaded: false,

  // Error state
  error: null,
};

// Action types (same as retrospective)
export const ActionTypes = {
  INITIALIZE_FILTERS: 'INITIALIZE_FILTERS',

  // Data loading
  SET_LOCATIONS: 'SET_LOCATIONS',
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

  // Lead-time bin metrics
  SET_LEAD_TIME_BIN_METRICS: 'SET_LEAD_TIME_BIN_METRICS',
  CLEAR_LEAD_TIME_BIN_METRICS: 'CLEAR_LEAD_TIME_BIN_METRICS',

  // Location metadata
  SET_LOCATION_METADATA: 'SET_LOCATION_METADATA',
  CLEAR_LOCATION_METADATA: 'CLEAR_LOCATION_METADATA',

  // CDF plots
  SET_CDF_PLOT_METRIC: 'SET_CDF_PLOT_METRIC',

  // Loading states
  SET_LOADING: 'SET_LOADING',

  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_MAP_VIEWPORT_BOUNDS: 'SET_MAP_VIEWPORT_BOUNDS',

  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

// Reducer function (same logic as retrospective)
const nwmdDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.INITIALIZE_FILTERS: {
      const { quarter, configuration, variable, threshold, aggMethod, leadTimeBin } =
        action.payload;

      const quarterToUse = state.mapFilters.quarter ?? quarter;
      const timeseriesSync = quarterToUse
        ? syncTimeseriesFiltersForQuarter(state.timeseriesFilters, quarterToUse)
        : {};

      return {
        ...state,

        mapFilters: {
          ...state.mapFilters,
          quarter: quarterToUse,
          configuration: state.mapFilters.configuration ?? configuration,
          variable: state.mapFilters.variable ?? variable,
          threshold:
            state.mapFilters.threshold !== undefined ? state.mapFilters.threshold : threshold,
          aggMethod: state.mapFilters.aggMethod ?? aggMethod,
          leadTimeBin: state.mapFilters.leadTimeBin ?? leadTimeBin,
        },

        timeseriesFilters: {
          ...state.timeseriesFilters,
          ...timeseriesSync,
          secondary: {
            ...state.timeseriesFilters.secondary,
            configurations:
              state.timeseriesFilters.secondary.configurations.length > 0
                ? state.timeseriesFilters.secondary.configurations
                : configuration
                  ? [configuration]
                  : [],
            variables:
              state.timeseriesFilters.secondary?.variables?.length > 0
                ? state.timeseriesFilters.secondary.variables
                : variable
                  ? [variable]
                  : [],
          },
        },
      };
    }

    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false,
      };

    case ActionTypes.SET_TABLE_PROPERTIES: {
      const tableProperties = action.payload || {};
      return {
        ...state,
        tableProperties,
        tablePropertiesLoading: false,
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
          configurations: action.payload.configuration ? [action.payload.configuration] : [],
        };
      }
      if (action.payload.variable !== undefined) {
        mapTimeseriesSync.primary = {
          ...state.timeseriesFilters.primary,
          variables: action.payload.variable ? [action.payload.variable] : [],
        };
        mapTimeseriesSync.secondary = {
          ...(mapTimeseriesSync.secondary || state.timeseriesFilters.secondary),
          variables: action.payload.variable ? [action.payload.variable] : [],
        };
      }
      if (action.payload.quarter !== undefined) {
        const quarterTimeseriesSync = syncTimeseriesFiltersForQuarter(
          state.timeseriesFilters,
          action.payload.quarter
        );
        mapTimeseriesSync.primary = {
          ...(mapTimeseriesSync.primary || state.timeseriesFilters.primary),
          ...quarterTimeseriesSync.primary,
        };
        mapTimeseriesSync.secondary = {
          ...(mapTimeseriesSync.secondary || state.timeseriesFilters.secondary),
          ...quarterTimeseriesSync.secondary,
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
            ...primary,
          },
          secondary: {
            ...state.timeseriesFilters.secondary,
            ...legacySecondary,
            ...secondary,
          },
        },
      };
    }

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

    case ActionTypes.SET_CDF_PLOT_METRIC:
      return {
        ...state,
        cdfPlots: {
          ...state.cdfPlots,
          [action.payload.plotId]: {
            ...state.cdfPlots[action.payload.plotId],
            metricName: action.payload.metricName,
          },
        },
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
      if ('metadata' in action.payload) {
        loadingUpdates.metadataLoading = action.payload.metadata;
      }
      if ('tablePropertiesLoading' in action.payload) {
        loadingUpdates.tablePropertiesLoading = action.payload.tablePropertiesLoading;
      }
      if ('leadTimeBinMetrics' in action.payload) {
        loadingUpdates.leadTimeBinMetricsLoading = action.payload.leadTimeBinMetrics;
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

    case ActionTypes.SET_MAP_VIEWPORT_BOUNDS:
      return {
        ...state,
        mapViewportBounds: action.payload || null,
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

    case ActionTypes.SET_LEAD_TIME_BIN_METRICS:
      return {
        ...state,
        leadTimeBinMetrics: action.payload,
        leadTimeBinMetricsLoading: false,
      };

    case ActionTypes.CLEAR_LEAD_TIME_BIN_METRICS:
      return {
        ...state,
        leadTimeBinMetrics: [],
        leadTimeBinMetricsLoading: false,
      };

    case ActionTypes.SET_LOCATION_METADATA:
      return {
        ...state,
        metadata: action.payload,
        metadataLoading: false,
      };

    case ActionTypes.CLEAR_LOCATION_METADATA:
      return {
        ...state,
        metadata: null,
        metadataLoading: false,
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
