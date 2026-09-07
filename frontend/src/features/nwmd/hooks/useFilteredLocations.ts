import { useMemo } from 'react';

import { useMetricLocations } from '@/shared/queries/metrics';
import type { MetricLocationsResponse } from '@/shared/types/metrics';
import type { MetricsFilters } from '@/shared/types/metrics';

import type { NwmdMapFilters } from '../types/maps';
import { applyAltHypothesisFilter } from '../utils/utils';

const hasApiFilters = (filters?: Record<string, unknown>) =>
  !!filters && Object.keys(filters).length > 0;

export const useFilteredLocations = (filters?: NwmdMapFilters) => {
  const { altHypothesis95, metricName, ...apiFilters } = filters || {};

  const locationsQuery = useMetricLocations(
    hasApiFilters(apiFilters) ? (apiFilters as MetricsFilters) : undefined
  );

  const filteredData = useMemo<MetricLocationsResponse | undefined>(() => {
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
