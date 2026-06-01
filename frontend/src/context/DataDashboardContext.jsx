/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

const initialDataState = {
  // Data
  locations: { features: [] },
  configurations: [],

  // Selected location
  selectedLocation: null,

  // Loading states
  locationsLoading: false,
  configsLoading: false,

  // Map state
  mapLoaded: false,
  mapFilters: {},

  // Error state
  error: null
};

export const ActionTypes = {
  SET_LOCATIONS: 'SET_LOCATIONS',
  SET_CONFIGURATIONS: 'SET_CONFIGURATIONS',
  SET_LOADING: 'SET_LOADING',
  SELECT_LOCATION: 'SELECT_LOCATION',
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR'
};

const dataDashboardReducer = (state, action) => {
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
        configurations: Array.isArray(action.payload) ? action.payload : [],
        configsLoading: false
      };

    case ActionTypes.SET_LOADING:
      return {
        ...state,
        ...action.payload
      };

    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload
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
        configsLoading: false
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

const DataDashboardContext = createContext(null);

export const DataDashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(dataDashboardReducer, initialDataState);
  return (
    <DataDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </DataDashboardContext.Provider>
  );
};

export const useDataDashboard = () => {
  const context = useContext(DataDashboardContext);
  if (!context) {
    throw new Error('useDataDashboard must be used within a DataDashboardProvider');
  }
  return context;
};
