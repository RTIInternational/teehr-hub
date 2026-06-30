import { useCallback } from 'react';
import { useGriddedDashboard, ActionTypes } from '../context/GriddedDashboardContext.jsx';
import { griddedApiService } from '../services/api.js';

export const useGriddedDataFetching = () => {
  const { state, dispatch } = useGriddedDashboard();

  const loadDatasets = useCallback(async () => {
    dispatch({ type: ActionTypes.SET_LOADING, payload: true });
    try {
      const data = await griddedApiService.getGriddedDatasets();
      dispatch({ type: ActionTypes.SET_DATASETS, payload: data.datasets ?? [] });
    } catch (err) {
      console.error('useGriddedDataFetching: Failed to load datasets:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load datasets: ${err.message}` });
    }
  }, [dispatch]);

  const loadVariables = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedVariables(datasetId);
      dispatch({ type: ActionTypes.SET_VARIABLES, payload: data.variables ?? [] });
    } catch (err) {
      console.error('useGriddedDataFetching: Failed to load variables:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load variables: ${err.message}` });
    }
  }, [dispatch]);

  const loadTimesteps = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedTimesteps(datasetId);
      dispatch({ type: ActionTypes.SET_TIMESTEPS, payload: data.values ?? [] });
    } catch (err) {
      console.error('useGriddedDataFetching: Failed to load timesteps:', err);
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Failed to load timesteps: ${err.message}` });
    }
  }, [dispatch]);

  const loadVariableAttrs = useCallback(async (datasetId) => {
    try {
      const data = await griddedApiService.getGriddedVariableAttrs(datasetId);
      dispatch({ type: ActionTypes.SET_VARIABLE_ATTRS, payload: data.variables ?? {} });
    } catch (err) {
      console.error('useGriddedDataFetching: Failed to load variable attrs:', err);
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
      console.error('useGriddedDataFetching: Timeseries query failed:', err);
      dispatch({ type: ActionTypes.SET_TIMESERIES_ERROR, payload: err.message });
    }
  }, [state.mapFilters.dataset, state.mapFilters.variable, state.timesteps, dispatch]);

  return { loadDatasets, loadVariables, loadTimesteps, loadVariableAttrs, runTimeseriesQuery };
};
