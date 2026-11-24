import { useCallback, useRef } from 'react';

import type { TeehrMapping } from '@/shared/api/gridded/variableAttrs';

import { useDashboard } from '../DashboardContext';
import { getVariableStyle } from '../utils/variableStyles';

export const useGriddedVariableStyles = () => {
  const { dispatch } = useDashboard();
  const styledVariablesRef = useRef<Set<string>>(new Set());

  const resetStyles = useCallback(() => {
    styledVariablesRef.current = new Set();
  }, []);

  // Styles are in teehr's names and units; the tiles take the range in the variable's stored units
  const applyVariableStyleIfNew = useCallback(
    (variable: string | null, mapping: TeehrMapping) => {
      if (!variable || styledVariablesRef.current.has(variable)) return;
      styledVariablesRef.current.add(variable);
      const { colorRamp, min, max } = getVariableStyle(mapping.variable);
      dispatch({
        type: 'UPDATE_MAP_FILTERS',
        payload: {
          colorRamp,
          colorRampMin: mapping.fromDisplay(min),
          colorRampMax: mapping.fromDisplay(max),
        },
      });
    },
    [dispatch]
  );

  return { resetStyles, applyVariableStyleIfNew };
};
