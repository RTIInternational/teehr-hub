import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

export type EventHeatmapFilters = {
  primaryLocationId: string | null;
  configurationName?: string | null;
  variableName?: string | null;
  threshold?: string | null;
};

// Each row returned by the event_heatmap collection
export type EventHeatmapRow = {
  primary_location_id: string;
  configuration_name: string;
  variable_name: string;
  event_id: string;
  forecast_lead_time_bin: string;
  relative_bias: number | null;
  root_mean_square_error: number | null;
  pearson_correlation: number | null;
  threshold: string | null;
  name: string;
  geometry: unknown;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

const TABLE = 'event_heatmap';

export const useEventHeatmap = (filters: EventHeatmapFilters) => {
  const { primaryLocationId, configurationName, variableName, threshold } = filters;

  return useQuery({
    queryKey: [
      'firo',
      'eventHeatmap',
      primaryLocationId,
      configurationName,
      variableName,
      threshold,
    ],
    queryFn: () =>
      apiService.getMetrics({
        table: TABLE,
        primary_location_id: primaryLocationId,
        configuration_name: configurationName ?? null,
        variable_name: variableName ?? null,
        threshold: threshold ?? null,
      }),
    enabled: !!primaryLocationId,
    select: (data) => extractFeatureProperties(data) as EventHeatmapRow[],
  });
};
