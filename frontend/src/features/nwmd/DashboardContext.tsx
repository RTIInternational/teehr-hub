/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from 'react';

import { NWMD_DASHBOARD_DEFAULTS } from '@/config/dashboardDefaults';
import type { MapLocation } from '@/shared/types/locations';
import type { MapMetric } from '@/shared/types/maps';
import type { TimeseriesFilters } from '@/shared/types/timeseries';
import { getQuarterDateRange } from '@/shared/utils/formatters';

import type { CdfPlots } from './types/cdf';
import type { NwmdMapFilters, ViewportBounds } from './types/maps';

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

const syncTimeseriesFiltersForQuarter = (timeseriesFilters: TimeseriesFilters, quarter: string) => {
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

export type DashboardState = {
  mapViewportBounds?: ViewportBounds;
  mapFilters: NwmdMapFilters;
  timeseriesFilters: TimeseriesFilters;
  selectedLocation: MapLocation | null;
  cdfPlotOrder: string[];
  cdfPlots: CdfPlots;
  mapLoaded: boolean;
  error: string | null;
};

type DashboardAction =
  | {
      type: typeof ActionTypes.INITIALIZE_FILTERS;
      payload: NwmdMapFilters;
    }
  | {
      type: typeof ActionTypes.UPDATE_MAP_FILTERS;
      payload: Partial<NwmdMapFilters>;
    }
  | {
      type: typeof ActionTypes.UPDATE_TIMESERIES_FILTERS;
      payload: Partial<TimeseriesFilters>;
    }
  | {
      type: typeof ActionTypes.SELECT_LOCATION;
      payload: MapLocation | null;
    }
  | {
      type: typeof ActionTypes.SET_CDF_PLOT_METRIC;
      payload: { plotId: string; metricName: MapMetric };
    }
  | {
      type: typeof ActionTypes.SET_MAP_LOADED;
      payload: boolean;
    }
  | {
      type: typeof ActionTypes.SET_MAP_VIEWPORT_BOUNDS;
      payload: ViewportBounds;
    }
  | {
      type: typeof ActionTypes.SET_ERROR;
      payload: string;
    }
  | {
      type: typeof ActionTypes.CLEAR_ERROR;
    };

// Initial state for nwmd dashboard
const initialState: DashboardState = {
  // Data
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

  // Map state
  mapLoaded: false,

  // Error state
  error: null,
};

// Action types (same as retrospective)
export const ActionTypes = {
  INITIALIZE_FILTERS: 'INITIALIZE_FILTERS',

  // Filter updates
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',

  // Location selection
  SELECT_LOCATION: 'SELECT_LOCATION',

  // CDF plots
  SET_CDF_PLOT_METRIC: 'SET_CDF_PLOT_METRIC',

  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_MAP_VIEWPORT_BOUNDS: 'SET_MAP_VIEWPORT_BOUNDS',

  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
} as const;

// Reducer function (same logic as retrospective)
const reducer = (state: DashboardState, action: DashboardAction) => {
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
            ...timeseriesSync.secondary,
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

    case ActionTypes.UPDATE_MAP_FILTERS: {
      // Keep timeseries defaults in sync with map display filters.
      // This mirrors retrospective behavior where map filter changes reset
      // the default timeseries selections.
      const mapTimeseriesSync: Partial<TimeseriesFilters> = {};
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
      if (action.payload.quarter) {
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
      return {
        ...state,
        timeseriesFilters: {
          ...state.timeseriesFilters,
          primary: {
            ...state.timeseriesFilters.primary,
            ...action.payload.primary,
          },
          secondary: {
            ...state.timeseriesFilters.secondary,
            ...action.payload.secondary,
          },
        },
      };
    }

    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload,
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

    default:
      return state;
  }
};

// Create context
type DashboardContextValue = {
  state: DashboardState;
  dispatch: Dispatch<DashboardAction>;
};

const DashboardContext = createContext<DashboardContextValue | null>(null);

// Provider component
export const DashboardProvider = ({ children }: React.PropsWithChildren) => {
  const [state, dispatch] = useReducer(reducer, initialState);

  return (
    <DashboardContext.Provider value={{ state, dispatch }}>{children}</DashboardContext.Provider>
  );
};

// Hook to use the context
export const useDashboard = () => {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useNwmdDashboard must be used within a NwmdDashboardProvider');
  }
  return context;
};

export default DashboardContext;
