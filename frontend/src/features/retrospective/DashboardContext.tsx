/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useReducer, type Dispatch } from 'react';
import { RETROSPECTIVE_DASHBOARD_DEFAULTS } from '@/config/dashboardDefaults';
import type { MapLocation } from '@/shared/types/locations';
import type { MapFilters } from '@/shared/types/maps';
import type { TimeseriesFiltersFlat } from '@/shared/types/timeseries';

export type DashboardState = {
  mapFilters: MapFilters;
  timeseriesFilters: TimeseriesFiltersFlat;
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
      payload: Partial<TimeseriesFiltersFlat>;
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

// Static date defaults for retrospective - uses 2020 data
const DEFAULT_START_DATE = RETROSPECTIVE_DASHBOARD_DEFAULTS.defaultStartDate;
const DEFAULT_END_DATE = RETROSPECTIVE_DASHBOARD_DEFAULTS.defaultEndDate;

// Initial state for retrospective dashboard
const initialState: DashboardState = {
  // Map filters (original structure)
  mapFilters: {
    configuration: null,
    variable: null,
    metricName: 'relative_bias',
  },

  // Timeseries filters (retrospective-specific defaults - year 2020)
  timeseriesFilters: {
    configurations: [], // Array for multi-select
    variable: null,
    start_date: DEFAULT_START_DATE,
    end_date: DEFAULT_END_DATE,
    reference_start_date: null,
    reference_end_date: null,
    duration: RETROSPECTIVE_DASHBOARD_DEFAULTS.preferredObservationsDuration,
  },

  // Selected location
  selectedLocation: null,

  // Map state
  mapLoaded: false,

  // Error state
  error: null,
};

// Action types (same as original)
export const ActionTypes = {
  // Data loading
  SET_CONFIGURATIONS: 'SET_CONFIGURATIONS',
  SET_VARIABLES: 'SET_VARIABLES',

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

// Reducer function (same logic as original)
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
          configurations:
            state.timeseriesFilters.configurations?.length > 0
              ? state.timeseriesFilters.configurations
              : configuration
                ? [configuration]
                : [],
          variable: state.timeseriesFilters.variable || variable,
        },
      };
    }

    case ActionTypes.UPDATE_MAP_FILTERS: {
      // NOTE: This behavior is intentionally mirrored in ForecastDashboardContext. // Keep map display and default timeseries filters aligned.
      const mapTimeseriesSync: Partial<TimeseriesFiltersFlat> = {};
      if (action.payload.configuration !== undefined) {
        // Sync map configuration to timeseries configurations array
        mapTimeseriesSync.configurations = action.payload.configuration
          ? [action.payload.configuration]
          : [];
      }
      if (action.payload.variable !== undefined) {
        mapTimeseriesSync.variable = action.payload.variable;
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
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
};

export default DashboardContext;
