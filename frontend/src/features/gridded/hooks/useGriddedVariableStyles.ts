import { useCallback, useRef } from 'react';

import { useDashboard } from '../DashboardContext';
import { getVariableStyle } from '../utils/variableStyles';

export const useGriddedVariableStyles = () => {
  const { dispatch } = useDashboard();
  const styledVariablesRef = useRef<Set<string>>(new Set());

  const resetStyles = useCallback(() => {
    styledVariablesRef.current = new Set();
  }, []);

  const applyVariableStyleIfNew = useCallback(
    (variable: string | null) => {
      if (!variable || styledVariablesRef.current.has(variable)) return;
      styledVariablesRef.current.add(variable);
      const { colorRamp, min, max } = getVariableStyle(variable);
      dispatch({
        type: 'UPDATE_MAP_FILTERS',
        payload: { colorRamp, colorRampMin: min, colorRampMax: max },
      });
    },
    [dispatch]
  );

  return { resetStyles, applyVariableStyleIfNew };
};
