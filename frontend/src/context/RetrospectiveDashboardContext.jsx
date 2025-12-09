/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

// Initial state for retrospective dashboard
const initialRetrospectiveState = {
  // Data
  locations: { features: [] },
  configurations: [],
  variables: [],
  metrics: [],
  
  // Map filters (original structure)
  mapFilters: {
    configuration: null,
    variable: null,
    metric: 'relative_bias'
  },
  
  // Timeseries filters (retrospective-specific defaults)
  timeseriesFilters: {
    configuration: null,
    variable: null,
    start_date: '2000-01-01T00:00',
    end_date: '2000-12-31T23:59',
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
  
  // Loading states
  locationsLoading: false,
  timeseriesLoading: false,
  
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
  SET_METRICS: 'SET_METRICS',
  
  // Filter updates
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  UPDATE_TIMESERIES_FILTERS: 'UPDATE_TIMESERIES_FILTERS',
  
  // Location selection
  SELECT_LOCATION: 'SELECT_LOCATION',
  
  // Timeseries data
  SET_PRIMARY_TIMESERIES: 'SET_PRIMARY_TIMESERIES',
  SET_SECONDARY_TIMESERIES: 'SET_SECONDARY_TIMESERIES',
  CLEAR_TIMESERIES: 'CLEAR_TIMESERIES',
  
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
      return {
        ...state,
        configurations,
        // Set defaults if first time loading
        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration || configurations[0]
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          configuration: state.timeseriesFilters.configuration || configurations[0]
        }
      };
      
    case ActionTypes.SET_VARIABLES:
      const variables = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        variables,
        // Set defaults if first time loading
        mapFilters: {
          ...state.mapFilters,
          variable: state.mapFilters.variable || variables[0]
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          variable: state.timeseriesFilters.variable || variables[0]
        }
      };
      
    case ActionTypes.SET_METRICS:
      const metrics = Array.isArray(action.payload) ? action.payload : [];
      return {
        ...state,
        metrics
      };
      
    case ActionTypes.UPDATE_MAP_FILTERS:
      return {
        ...state,
        mapFilters: {
          ...state.mapFilters,
          ...action.payload
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
        },
        timeseriesLoading: false
      };
      
    case ActionTypes.SET_SECONDARY_TIMESERIES:
      return {
        ...state,
        timeseriesData: {
          ...state.timeseriesData,
          secondary: action.payload
        }
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
      return {
        ...state,
        ...action.payload
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