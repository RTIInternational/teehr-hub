import { useQuery } from '@tanstack/react-query';

import { getMetrics, type MetricsFilters } from '@/shared/api/metrics';

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
    queryFn: () => getMetrics(filters),
    enabled: hasRequiredFilters(filters ?? {}),
    select: (metricsData) =>
      (metricsData?.features || []).map((feature) => feature?.properties || {}),
  });
