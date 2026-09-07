import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

import type { MetricLocationsResponse } from '../types/metrics';
import type { MetricsFilters } from '../types/metrics';

export const useMetricsByLocation = (primaryLocationId: string | null, table: string | null) =>
  useQuery({
    queryKey: ['locationMetrics', primaryLocationId, table],
    queryFn: () => apiService.getMetrics({ primary_location_id: primaryLocationId, table: table }),
    enabled: !!primaryLocationId && !!table,
    select: extractFeatureProperties,
  });
export const useMetricLocations = (filters?: MetricsFilters) =>
  useQuery<MetricLocationsResponse>({
    queryKey: ['locations', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: !!filters,
  });
