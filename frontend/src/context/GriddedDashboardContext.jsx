/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useReducer } from 'react';

const initialGriddedState = {
  datasets: [],       // string[] — available dataset names from xpublish
  variables: [],      // string[] — variables for the selected dataset
  timesteps: [],      // string[] — ISO datetime strings for selected dataset+variable

  mapFilters: {
    dataset: null,
    variable: null,
    timestepIndex: 0,
    colorRamp: 'raster/plasma',
    colorRampMin: 0,
    colorRampMax: 100,
  },

  activeOverlays: [],   // string[] of overlay IDs currently shown on the map

  mapLoaded: false,
  loading: false,
  error: null,
};

export const ActionTypes = {
  SET_DATASETS: 'SET_DATASETS',
  SET_VARIABLES: 'SET_VARIABLES',
  SET_TIMESTEPS: 'SET_TIMESTEPS',
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  TOGGLE_OVERLAY: 'TOGGLE_OVERLAY',
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
};

const griddedDashboardReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_DATASETS:
      return {
        ...state,
        datasets: Array.isArray(action.payload) ? action.payload : [],
        loading: false,
      };

    case ActionTypes.SET_VARIABLES:
      return {
        ...state,
        variables: Array.isArray(action.payload) ? action.payload : [],
        // Reset variable and timestep when the dataset changes
        mapFilters: {
          ...state.mapFilters,
          variable: action.payload?.[0] ?? null,
          timestepIndex: 0,
        },
        timesteps: [],
      };

    case ActionTypes.SET_TIMESTEPS:
      return {
        ...state,
        timesteps: Array.isArray(action.payload) ? action.payload : [],
        mapFilters: {
          ...state.mapFilters,
          timestepIndex: 0,
        },
      };

    case ActionTypes.UPDATE_MAP_FILTERS:
      return {
        ...state,
        mapFilters: {
          ...state.mapFilters,
          ...action.payload,
        },
      };

    case ActionTypes.TOGGLE_OVERLAY: {
      const id = action.payload;
      const next = state.activeOverlays.includes(id)
        ? state.activeOverlays.filter((x) => x !== id)
        : [...state.activeOverlays, id];
      return { ...state, activeOverlays: next };
    }

    case ActionTypes.SET_MAP_LOADED:
      return { ...state, mapLoaded: action.payload };

    case ActionTypes.SET_LOADING:
      return { ...state, loading: action.payload };

    case ActionTypes.SET_ERROR:
      return { ...state, error: action.payload, loading: false };

    case ActionTypes.CLEAR_ERROR:
      return { ...state, error: null };

    default:
      return state;
  }
};

const GriddedDashboardContext = createContext(null);

export const GriddedDashboardProvider = ({ children }) => {
  const [state, dispatch] = useReducer(griddedDashboardReducer, initialGriddedState);
  return (
    <GriddedDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </GriddedDashboardContext.Provider>
  );
};

export const useGriddedDashboard = () => {
  const context = useContext(GriddedDashboardContext);
  if (!context) {
    throw new Error('useGriddedDashboard must be used within a GriddedDashboardProvider');
  }
  return context;
};
