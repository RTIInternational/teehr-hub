import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

export type LeadTimeMetricsFilters = {
  primaryLocationId: string | null;
  season?: string | null;
  threshold?: string | null; // observed flow quantile column is named "threshold" in the table
};

// Each row returned by the locations_metrics collection
export type LeadTimeMetricsRow = {
  primary_location_id: string;
  configuration_name: string;
  variable_name: string;
  season: string | null;
  forecast_lead_time_bin: string;
  threshold: string | null;
  forecast_lead_time: number; // seconds
  mean_absolute_error: number | null;
  root_mean_square_error: number | null;
  relative_bias: number | null;
  pearson_correlation: number | null;
  [key: string]: unknown;
};

const TABLE = 'locations_metrics';

export const useLeadTimeMetrics = (filters: LeadTimeMetricsFilters) => {
  const { primaryLocationId, season, threshold } = filters;

  return useQuery({
    queryKey: ['firo', 'leadTimeMetrics', primaryLocationId, season, threshold],
    queryFn: () =>
      apiService.getMetrics({
        table: TABLE,
        primary_location_id: primaryLocationId,
        season: season ?? null,
        threshold: threshold ?? null,
      }),
    enabled: !!primaryLocationId,
    select: (data) => extractFeatureProperties(data) as LeadTimeMetricsRow[],
  });
};
