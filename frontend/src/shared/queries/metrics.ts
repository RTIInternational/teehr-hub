import { useQuery } from '@tanstack/react-query';
import { apiService } from '@/services/api';
import { extractFeatureProperties } from '@/shared/utils/ogcTransformers';

export const useLocationMetrics = (primaryLocationId: string | null, table: string | null) =>
  useQuery({
    queryKey: ['locationMetrics', primaryLocationId, table],
    queryFn: () => apiService.getMetrics({ primary_location_id: primaryLocationId, table: table }),
    enabled: !!primaryLocationId && !!table,
    select: extractFeatureProperties,
  });
