import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

export type EventRankingsFilters = {
  primaryLocationId: string | null;
  configurationName?: string | null;
  variableName?: string | null;
  threshold?: string | null;
};

// Each row returned by the event_rankings collection
export type EventRankingRow = {
  primary_location_id: string;
  configuration_name: string;
  variable_name: string;
  event_above_id: string | null;
  event_above_peak_rank: number | null;
  peak_value: number | null;
  threshold: string | null;
  name: string;
  geometry: unknown;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

const TABLE = 'event_rankings';

export const useEventRankings = (filters: EventRankingsFilters) => {
  const { primaryLocationId, configurationName, variableName, threshold } = filters;

  return useQuery({
    queryKey: [
      'firo',
      'eventRankings',
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
    select: (data) => extractFeatureProperties(data) as EventRankingRow[],
  });
};
