import { skipToken, useQuery } from '@tanstack/react-query';

import { getMetrics, type MetricsFilters } from '@/shared/api/metrics';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

export const useMetricsByLocation = (primaryLocationId: string | null, table: string | null) =>
  useQuery({
    queryKey: ['locationMetrics', primaryLocationId, table],
    queryFn:
      primaryLocationId && table
        ? () => getMetrics({ primary_location_id: primaryLocationId, table: table })
        : skipToken,
    select: (data) => (data ? extractFeatureProperties(data) : []),
  });

export const useMetricLocations = (filters?: MetricsFilters) =>
  useQuery({
    queryKey: ['locations', filters],
    queryFn: () => getMetrics(filters),
    enabled: !!filters,
  });
