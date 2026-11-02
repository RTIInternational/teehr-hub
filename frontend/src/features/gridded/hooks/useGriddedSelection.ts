import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

import { useDatasetMetadata } from '@/shared/queries/gridded/datasets';
import { coordValuesQueryOptions } from '@/shared/queries/gridded/timesteps';
import { parseUtcTime } from '@/shared/utils/dates';

import { useDashboard } from '../DashboardContext';
import { useCurrentTimestep } from './useCurrentTimestep';

const LEAD_TIME = 'lead_time';
const NO_DIMS: string[] = [];

// Which map the active dataset shows. An analysis dataset is picked by its time step alone; a
// forecast also by a value on each axis after its cycle (lead time, member), the first value
// until one is chosen. `selectors` are the tile request's dimension selectors, null until complete.
export const useGriddedSelection = () => {
  const { state } = useDashboard();
  const { dataset, fixedSelections } = state.mapFilters;
  const metadata = useDatasetMetadata(dataset);
  const currentTimestep = useCurrentTimestep();

  const appendDim = metadata.data?.append_dim ?? null;
  const fixedDims = metadata.data?.fixed_dims ?? NO_DIMS;
  const valueQueries = useQueries({
    queries: fixedDims.map((dim) => coordValuesQueryOptions(dataset, dim)),
  });
  const values: Record<string, string[]> = Object.fromEntries(
    fixedDims.map((dim, i) => [dim, valueQueries[i]?.data ?? []])
  );
  const selected: Record<string, string> = Object.fromEntries(
    fixedDims
      .map((dim) => [dim, fixedSelections[dim] ?? values[dim][0]] as const)
      .filter(([, value]) => value !== undefined)
  );

  // Memoized on strings, so the map redraws only when the selection changes
  const selectedKey = new URLSearchParams(selected).toString();
  const complete = fixedDims.every((dim) => dim in selected);
  const selectors = useMemo(
    () =>
      appendDim && currentTimestep && complete
        ? { [appendDim]: currentTimestep, ...Object.fromEntries(new URLSearchParams(selectedKey)) }
        : null,
    [appendDim, currentTimestep, complete, selectedKey]
  );

  const lead = selected[LEAD_TIME];
  const validTime =
    currentTimestep && lead !== undefined
      ? new Date(parseUtcTime(currentTimestep) + Number(lead) * 3600 * 1000)
          .toISOString()
          .slice(0, 19)
      : null;

  return { appendDim, fixedDims, values, selected, selectors, validTime };
};
