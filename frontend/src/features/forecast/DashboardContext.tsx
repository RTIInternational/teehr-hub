/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from 'react';

import { FORECAST_DASHBOARD_DEFAULTS } from '@/config/dashboardDefaults';
import type { MapLocation } from '@/shared/types/locations';
import type { MapFilters } from '@/shared/types/maps';
import type { TimeseriesFilters } from '@/shared/types/timeseries';

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

export type DashboardState = {
  mapFilters: MapFilters;
  timeseriesFilters: TimeseriesFilters;
  selectedLocation: MapLocation | null;
  mapLoaded: boolean;
  error: string | null;
};

type DashboardAction =
  | {
      type: typeof ActionTypes.INITIALIZE_FILTERS;
      payload: { configuration: string | null; variable: string | null };
    }
  | {
      type: typeof ActionTypes.UPDATE_MAP_FILTERS;
      payload: Partial<MapFilters>;
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
      type: typeof ActionTypes.SET_MAP_LOADED;
      payload: boolean;
    }
  | {
      type: typeof ActionTypes.SET_ERROR;
      payload: string;
    }
  | {
      type: typeof ActionTypes.CLEAR_ERROR;
    };

// Initial state for forecast dashboard
const initialState: DashboardState = {
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
  // Filter updates
  INITIALIZE_FILTERS: 'INITIALIZE_FILTERS',
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',

  // Location selection
  SELECT_LOCATION: 'SELECT_LOCATION',

  // Map state
  SET_MAP_LOADED: 'SET_MAP_LOADED',

  // Error handling
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
} as const;

// Reducer function (same logic as retrospective)
const reducer = (state: DashboardState, action: DashboardAction) => {
  switch (action.type) {
    case ActionTypes.INITIALIZE_FILTERS: {
      const { configuration, variable } = action.payload;

      return {
        ...state,

        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration ?? configuration,
          variable: state.mapFilters.variable ?? variable,
        },

        timeseriesFilters: {
          ...state.timeseriesFilters,
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

    case ActionTypes.UPDATE_MAP_FILTERS: {
      // the default timeseries selections. // This mirrors retrospective behavior where map filter changes reset // Keep timeseries defaults in sync with map display filters.
      const mapTimeseriesSync: Partial<TimeseriesFilters> = {};
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
    throw new Error('useForecastDashboard must be used within a ForecastDashboardProvider');
  }
  return context;
};

export default DashboardContext;
