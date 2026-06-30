import { useEffect, useCallback, useRef } from 'react';
import { useGriddedDashboard, ActionTypes } from '../../../context/GriddedDashboardContext.jsx';
import { griddedApiService } from '../../../services/api.js';
import { getVariableStyle } from './variableStyles.js';
import DashboardPanel from '../../common/dashboard/DashboardPanel.jsx';
import GriddedMapComponent from './GriddedMapComponent.jsx';
import GriddedControls from './GriddedControls.jsx';
import GriddedTimeseriesPanel from './GriddedTimeseriesPanel.jsx';

const Dashboard = () => {
  const { state, dispatch } = useGriddedDashboard();
  const styledVariablesRef = useRef(new Set());

  const loadDatasets = useCallback(async () => {
    dispatch({ type: ActionTypes.SET_LOADING, payload: true });
    try {
      const data = await griddedApiService.getGriddedDatasets();
      dispatch({ type: ActionTypes.SET_DATASETS, payload: data.datasets ?? [] });
    } catch (err) {
      console.error('GriddedDashboard: Failed to load datasets:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load datasets: ${err.message}` });
    }
  }, [dispatch]);

  const loadVariables = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedVariables(datasetId);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: data.variables ?? [] });
    } catch (err) {
      console.error('GriddedDashboard: Failed to load variables:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${err.message}` });
    }
  }, [dispatch]);

  const loadTimesteps = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedTimesteps(datasetId);
      dispatch({ type: ActionTypes.SET_TIMESTEPS, payload: data.values ?? [] });
    } catch (err) {
      console.error('GriddedDashboard: Failed to load timesteps:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timesteps: ${err.message}` });
    }
  }, [dispatch]);

  const loadVariableAttrs = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedVariableAttrs(datasetId);
      dispatch({ type: ActionTypes.SET_VARIABLE_ATTRS, payload: data.variables ?? {} });
    } catch (err) {
      console.error('GriddedDashboard: Failed to load variable attrs:', err);
    }
  }, [dispatch]);

  const runTimeseriesQuery = useCallback(async (lon, lat) => {
    const { dataset, variable } = state.mapFilters;
    const { timesteps } = state;
    if (!dataset || !variable || timesteps.length === 0) return;
    dispatch({ type: ActionTypes.SET_TIMESERIES_LOADING, payload: true });
    try {
      const data = await griddedApiService.fetchGriddedEdrTimeseries(dataset, variable, lon, lat, timesteps);
      dispatch({ type: ActionTypes.SET_TIMESERIES_DATA, payload: { ...data, lon, lat, variable } });
    } catch (err) {
      console.error('GriddedDashboard: Timeseries query failed:', err);
      dispatch({ type: ActionTypes.SET_TIMESERIES_ERROR, payload: err.message });
    }
  }, [state.mapFilters.dataset, state.mapFilters.variable, state.timesteps, dispatch]);

  // Load datasets on mount
  useEffect(() => {
    loadDatasets();
  }, [loadDatasets]);

  // Auto-load variables when a dataset is first set
  useEffect(() => {
    const { dataset } = state.mapFilters;
    if (dataset && state.variables.length === 0) {
      loadVariables(dataset);
    }
  }, [state.mapFilters.dataset, state.variables.length, loadVariables]);

  // Auto-load timesteps when a variable is first set
  useEffect(() => {
    const { dataset, variable } = state.mapFilters;
    if (dataset && variable && state.timesteps.length === 0) {
      loadTimesteps(dataset, variable);
    }
  }, [state.mapFilters.dataset, state.mapFilters.variable, state.timesteps.length, loadTimesteps]);

  // Run timeseries query when the user clicks a point on the map
  useEffect(() => {
    if (state.clickedPoint) {
      runTimeseriesQuery(state.clickedPoint.lon, state.clickedPoint.lat);
    }
  }, [state.clickedPoint, runTimeseriesQuery]);

  // Fetch variable attrs and reset style-tracking when dataset changes
  useEffect(() => {
    if (state.mapFilters.dataset) {
      loadVariableAttrs(state.mapFilters.dataset);
      styledVariablesRef.current = new Set();
    }
  }, [state.mapFilters.dataset, loadVariableAttrs]);

  // Auto-apply variable-specific default styles on first selection of each variable
  useEffect(() => {
    const { variable } = state.mapFilters;
    if (!variable || styledVariablesRef.current.has(variable)) return;
    styledVariablesRef.current.add(variable);
    const { colorRamp, min, max } = getVariableStyle(variable);
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { colorRamp, colorRampMin: min, colorRampMax: max } });
  }, [state.mapFilters.variable, dispatch]);

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)', minHeight: 0 }}>
      <div className="container-fluid flex-grow-1 p-0" style={{ minHeight: 0, overflow: 'hidden' }}>
        <div
          className="dashboard-grid h-100"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gridTemplateRows: 'auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.8fr)',
            gap: '12px',
            padding: '12px',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {/* Error banner */}
          {state.error && (
            <div
              className="alert alert-danger alert-dismissible"
              role="alert"
              style={{ gridColumn: '1 / -1', gridRow: '1 / 2', zIndex: 1000, margin: 0 }}
            >
              <i className="bi bi-exclamation-triangle-fill me-2"></i>
              <strong>Error:</strong> {state.error}
              <button
                type="button"
                className="btn-close"
                onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })}
                aria-label="Close"
              ></button>
            </div>
          )}

          {/* Map panel — upper left */}
          <div
            className="map-panel"
            style={{
              gridColumn: '1 / 2',
              gridRow: state.error ? '2 / 4' : '1 / 4',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              position: 'relative',
              minHeight: 0,
            }}
          >
            <GriddedMapComponent />
          </div>

          {/* Controls panel — upper right */}
          <div
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '2 / 3' : '1 / 2',
              minHeight: 0,
            }}
          >
            <DashboardPanel header={<span className="small fw-bold">Display Options</span>} bodyStyle={{ padding: '8px' }}>
              <GriddedControls
                loadVariables={loadVariables}
                loadTimesteps={loadTimesteps}
              />
            </DashboardPanel>
          </div>

          {/* Bottom full-width panel — timeseries plot */}
          <div
            style={{
              gridColumn: '1 / -1',
              gridRow: state.error ? '5 / 6' : '4 / 5',
              minHeight: 0,
            }}
          >
            <GriddedTimeseriesPanel />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
