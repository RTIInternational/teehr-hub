import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

import type { LocationMetadataResponse } from '../types/locations';

export const useLocationMetadata = (primaryLocationId?: string | null) =>
  useQuery<LocationMetadataResponse>({
    queryKey: ['locationMetadata', primaryLocationId],
    queryFn: () => apiService.getLocationById(primaryLocationId, true),
    enabled: !!primaryLocationId,
  });
