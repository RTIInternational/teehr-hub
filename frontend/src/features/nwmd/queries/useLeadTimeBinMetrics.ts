import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import type { MetricsFilters } from '@/shared/types/metrics';

type LeadTimeBinFilters = Partial<MetricsFilters> & {
  primary_location_id?: string | null;
  waterYear?: string | null;
  quarter?: string | null;
  threshold?: string | null;
  aggMethod?: string | null;
};

const hasRequiredFilters = (filters: LeadTimeBinFilters) =>
  !!filters.table &&
  !!filters.primary_location_id &&
  !!filters.configuration &&
  !!filters.variable &&
  filters.waterYear !== undefined &&
  filters.quarter !== undefined &&
  filters.threshold !== undefined &&
  !!filters.aggMethod;

export const useLeadTimeBinMetrics = (filters?: LeadTimeBinFilters) =>
  useQuery({
    queryKey: ['leadTimeBinMetrics', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: hasRequiredFilters(filters ?? {}),
    select: (metricsData) =>
      (metricsData?.features || []).map((feature) => feature?.properties || {}),
  });
