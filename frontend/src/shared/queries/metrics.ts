import { skipToken, useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

import type { MetricsFilters } from '../types/metrics';

export const useMetricsByLocation = (primaryLocationId: string | null, table: string | null) =>
  useQuery({
    queryKey: ['locationMetrics', primaryLocationId, table],
    queryFn:
      primaryLocationId && table
        ? () => apiService.getMetrics({ primary_location_id: primaryLocationId, table: table })
        : skipToken,
    select: (data) => (data ? extractFeatureProperties(data) : []),
  });

export const useMetricLocations = (filters?: MetricsFilters) =>
  useQuery({
    queryKey: ['locations', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: !!filters,
  });
