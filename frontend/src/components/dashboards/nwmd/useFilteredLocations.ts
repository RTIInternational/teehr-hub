import { useMemo } from 'react';

import { useLocations } from '@/shared/queries/locations';
import type { LocationsResponse } from '@/shared/types/locations';
import type { MetricsFilters } from '@/shared/types/metrics';

import { applyAltHypothesisFilter } from './utils';

type AltHypothesisOperator = '=0' | '!=0' | '>0' | '<0' | '>1' | '<1';

export type NwmdFilters = Partial<MetricsFilters> & {
  quarter?: string | null;
  threshold?: string | null;
  aggMethod?: string | null;
  leadTimeBin?: string | null;
  metricName?: string | null;
  altHypothesis95?: AltHypothesisOperator | null;
};

const hasApiFilters = (filters?: Record<string, unknown>) =>
  !!filters && Object.keys(filters).length > 0;

export const useFilteredLocations = (filters?: NwmdFilters) => {
  const { altHypothesis95, metricName, ...apiFilters } = filters || {};

  const locationsQuery = useLocations(
    hasApiFilters(apiFilters) ? (apiFilters as MetricsFilters) : undefined
  );

  const filteredData = useMemo<LocationsResponse | undefined>(() => {
    const rawData = locationsQuery.data;
    if (!rawData) return rawData;

    return applyAltHypothesisFilter(rawData, metricName ?? undefined, altHypothesis95 ?? undefined);
  }, [locationsQuery.data, metricName, altHypothesis95]);

  return {
    ...locationsQuery,
    data: filteredData,
    rawData: locationsQuery.data,
  };
};
