import { useMemo } from 'react';

import { useMetricLocations } from '@/shared/queries/metrics';
import type { MetricsFilters } from '@/shared/types/metrics';

import type { NwmdMapFilters } from '../types/maps';
import { applyAltHypothesisFilter } from '../utils/utils';

// Wait for the defaults to load; without them the request would scan the whole table.
// A null waterYear is the "<all>" option, so only undefined means not yet initialized.
const hasRequiredFilters = (filters: NwmdMapFilters) =>
  !!filters.table &&
  !!filters.configuration &&
  !!filters.variable &&
  filters.waterYear !== undefined;

export const useFilteredLocations = (filters?: NwmdMapFilters) => {
  const { altHypothesis95, metricName, ...apiFilters } = filters || {};

  const locationsQuery = useMetricLocations(
    hasRequiredFilters(apiFilters) ? (apiFilters as MetricsFilters) : undefined
  );

  const filteredData = useMemo(() => {
    const rawData = locationsQuery.data;
    if (!rawData || !metricName || !altHypothesis95) return rawData;

    return applyAltHypothesisFilter(rawData, metricName, altHypothesis95);
  }, [locationsQuery.data, metricName, altHypothesis95]);

  return {
    ...locationsQuery,
    data: filteredData,
    rawData: locationsQuery.data,
  };
};
