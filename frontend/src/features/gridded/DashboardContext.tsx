import { createContext, useContext, useReducer, type Dispatch } from 'react';

import type { ClickedPoint, MapFilters, SelectedLocation } from '@/shared/types/gridded/maps';
import type { PolygonFeatures } from '@/shared/types/gridded/tiles';

import type { GriddedTabName } from './Dashboard';

type PolygonFeaturesPayload = { features: PolygonFeatures; lngLat: ClickedPoint };

export type DashboardState = {
  mapFilters: MapFilters;
  activeOverlays: string[];
  activePolygonLayer: string | null;
  rightPanelTab: GriddedTabName;
  polygonFeatures: PolygonFeatures;
  polygonClickLngLat: ClickedPoint | null;
  selectedLocation: SelectedLocation | null;
  clickedPoint: ClickedPoint | null;
  mapLoaded: boolean;
  loading: boolean;
  error: string | null;
};

type UpdateMapFiltersPayload = Partial<MapFilters>;

const initialState: DashboardState = {
  mapFilters: {
    dataset: null,
    variable: null,
    timestepIndex: 0,
    colorRamp: 'raster/plasma',
    colorRampMin: 0,
    colorRampMax: 100,
  },

  activeOverlays: [], // string[] of overlay IDs currently shown on the map

  // Polygon layers from S3/pmtiles
  activePolygonLayer: null, // string (layer id) | null — exclusive selection

  // Which tab the right-hand panel shows. Lives here rather than in local state
  // because a map click needs to bring the polygon tab forward.
  rightPanelTab: 'dataset', // 'dataset' | 'polygons'

  // Every polygon under the last map click, including nested/overlapping ones
  polygonFeatures: [], // [{ id, name, ... }] — deduped feature properties
  polygonClickLngLat: null, // { lon, lat } | null — where the polygons were picked
  selectedLocation: null, // { primary_location_id, name } | null — feature chosen for a warehouse query

  clickedPoint: null, // { lon, lat } | null — last point clicked on the map

  mapLoaded: false,
  loading: false,
  error: null,
};

export const ActionTypes = {
  SET_TIMESTEPS: 'SET_TIMESTEPS',
  UPDATE_MAP_FILTERS: 'UPDATE_MAP_FILTERS',
  TOGGLE_OVERLAY: 'TOGGLE_OVERLAY',
  SET_ACTIVE_POLYGON_LAYER: 'SET_ACTIVE_POLYGON_LAYER',
  SET_RIGHT_PANEL_TAB: 'SET_RIGHT_PANEL_TAB',
  SET_POLYGON_FEATURES: 'SET_POLYGON_FEATURES',
  CLEAR_POLYGON_FEATURES: 'CLEAR_POLYGON_FEATURES',
  SELECT_LOCATION: 'SELECT_LOCATION',
  SET_CLICKED_POINT: 'SET_CLICKED_POINT',
  SET_MAP_LOADED: 'SET_MAP_LOADED',
  SET_LOADING: 'SET_LOADING',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
} as const;

export type DashboardAction =
  | { type: typeof ActionTypes.UPDATE_MAP_FILTERS; payload: UpdateMapFiltersPayload }
  | { type: typeof ActionTypes.TOGGLE_OVERLAY; payload: string }
  | { type: typeof ActionTypes.SET_ACTIVE_POLYGON_LAYER; payload: string | null }
  | { type: typeof ActionTypes.SET_RIGHT_PANEL_TAB; payload: GriddedTabName }
  | { type: typeof ActionTypes.SET_POLYGON_FEATURES; payload: PolygonFeaturesPayload }
  | { type: typeof ActionTypes.CLEAR_POLYGON_FEATURES }
  | { type: typeof ActionTypes.SELECT_LOCATION; payload: SelectedLocation }
  | { type: typeof ActionTypes.SET_CLICKED_POINT; payload: ClickedPoint | null }
  | { type: typeof ActionTypes.SET_MAP_LOADED; payload: boolean }
  | { type: typeof ActionTypes.SET_LOADING; payload: boolean }
  | { type: typeof ActionTypes.SET_ERROR; payload: string | null }
  | { type: typeof ActionTypes.CLEAR_ERROR };

const reducer = (state: DashboardState, action: DashboardAction): DashboardState => {
  switch (action.type) {
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
        : [id];
      return { ...state, activeOverlays: next };
    }

    case ActionTypes.SET_ACTIVE_POLYGON_LAYER:
      return {
        ...state,
        activePolygonLayer: action.payload,
        // Features from the previous layer no longer apply
        polygonFeatures: [],
        polygonClickLngLat: null,
        selectedLocation: null,
      };

    case ActionTypes.SET_RIGHT_PANEL_TAB:
      return { ...state, rightPanelTab: action.payload };

    case ActionTypes.SET_POLYGON_FEATURES:
      return {
        ...state,
        polygonFeatures: Array.isArray(action.payload?.features) ? action.payload.features : [],
        polygonClickLngLat: action.payload?.lngLat ?? null,
        selectedLocation: null,
        // Bring the results forward — otherwise the click looks like a no-op
        rightPanelTab: 'polygons',
      };

    case ActionTypes.CLEAR_POLYGON_FEATURES:
      return {
        ...state,
        polygonFeatures: [],
        polygonClickLngLat: null,
        selectedLocation: null,
      };

    case ActionTypes.SELECT_LOCATION:
      return {
        ...state,
        selectedLocation: action.payload,
      };

    case ActionTypes.SET_CLICKED_POINT:
      return {
        ...state,
        clickedPoint: action.payload,
      };

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

export type DashboardContextValue = {
  state: DashboardState;
  dispatch: Dispatch<DashboardAction>;
};

const GriddedDashboardContext = createContext<DashboardContextValue | undefined>(undefined);

export const DashboardProvider = ({ children }: React.PropsWithChildren) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <GriddedDashboardContext.Provider value={{ state, dispatch }}>
      {children}
    </GriddedDashboardContext.Provider>
  );
};

export const useDashboard = () => {
  const context = useContext(GriddedDashboardContext);
  if (!context) {
    throw new Error('useGriddedDashboard must be used within a GriddedDashboardProvider');
  }
  return context;
};
