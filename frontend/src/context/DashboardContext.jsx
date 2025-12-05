/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

// Initial state
const initialState = {
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
  
  // Timeseries filters (separate)
  timeseriesFilters: {
    configuration: null,
    variable: null,
    start_date: null,
    end_date: null,
    reference_time: null
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

// Action types
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

// Reducer function
const dashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_LOCATIONS:
      return {
        ...state,
        locations: action.payload,
        locationsLoading: false
      };
      
    case ActionTypes.SET_CONFIGURATIONS:
      return {
        ...state,
        configurations: action.payload,
        // Set defaults if first time loading
        mapFilters: {
          ...state.mapFilters,
          configuration: state.mapFilters.configuration || action.payload[0]
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          configuration: state.timeseriesFilters.configuration || action.payload[0]
        }
      };
      
    case ActionTypes.SET_VARIABLES:
      return {
        ...state,
        variables: action.payload,
        // Set defaults if first time loading
        mapFilters: {
          ...state.mapFilters,
          variable: state.mapFilters.variable || action.payload[0]
        },
        timeseriesFilters: {
          ...state.timeseriesFilters,
          variable: state.timeseriesFilters.variable || action.payload[0]
        }
      };
      
    case ActionTypes.SET_METRICS:
      return {
        ...state,
        metrics: action.payload
      };
      
    case ActionTypes.UPDATE_MAP_FILTERS:
      return {
        ...state,
        mapFilters: { ...state.mapFilters, ...action.payload }
      };
      
    case ActionTypes.UPDATE_TIMESERIES_FILTERS:
      return {
        ...state,
        timeseriesFilters: { ...state.timeseriesFilters, ...action.payload }
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
      return {
        ...state,
        locationsLoading: action.payload.locations !== undefined ? action.payload.locations : state.locationsLoading,
        timeseriesLoading: action.payload.timeseries !== undefined ? action.payload.timeseries : state.timeseriesLoading
      };
      
    case ActionTypes.SET_MAP_LOADED:
      return {
        ...state,
        mapLoaded: action.payload
      };
      
    case ActionTypes.SET_ERROR:
      return {
        ...state,
        error: action.payload,
        locationsLoading: false,
        timeseriesLoading: false
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
const DashboardContext = createContext();

// Provider component
export const DashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(dashboardReducer, initialState);
  
  return (
    <DashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </DashboardContext.Provider>
  );
};

// Custom hook to use the dashboard context
export const useDashboard = () => {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error('useDashboard must be used within a DashboardProvider');
  }
  return context;
};

export default DashboardContext;