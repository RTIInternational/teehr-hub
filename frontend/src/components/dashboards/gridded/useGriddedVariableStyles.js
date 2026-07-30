import { useCallback, useRef } from 'react';
import { useGriddedDashboard, ActionTypes } from '../../../context/GriddedDashboardContext.jsx';
import { getVariableStyle } from './variableStyles.js';

export const useGriddedVariableStyles = () => {
  const { dispatch } = useGriddedDashboard();
  const styledVariablesRef = useRef(new Set());

  const resetStyles = useCallback(() => {
    styledVariablesRef.current = new Set();
  }, []);

  const applyVariableStyleIfNew = useCallback((variable) => {
    if (!variable || styledVariablesRef.current.has(variable)) return;
    styledVariablesRef.current.add(variable);
    const { colorRamp, min, max } = getVariableStyle(variable);
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { colorRamp, colorRampMin: min, colorRampMax: max } });
  }, [dispatch]);

  return { resetStyles, applyVariableStyleIfNew };
};
