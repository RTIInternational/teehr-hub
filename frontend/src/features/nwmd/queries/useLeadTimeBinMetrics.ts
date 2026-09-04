import { useQuery } from '@tanstack/react-query';
import type { FeatureCollection, Point } from 'geojson';

import { apiService } from '@/services/api';
import type { MetricsFilters } from '@/shared/types/metrics';

type LeadTimeBinFilters = Partial<MetricsFilters> & {
  primary_location_id?: string | null;
  quarter?: string | null;
  threshold?: string | null;
  aggMethod?: string | null;
};

export const useLeadTimeBinMetrics = (filters?: LeadTimeBinFilters) =>
  useQuery({
    queryKey: ['leadTimeBinMetrics', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: !!filters,
    select: (metricsData: FeatureCollection<Point>) =>
      (metricsData?.features || []).map((feature) => feature?.properties || {}),
  });
