import { skipToken, useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

export const useLocationMetadata = (primaryLocationId?: string | null) =>
  useQuery({
    queryKey: ['locationMetadata', primaryLocationId],
    queryFn: primaryLocationId
      ? () => apiService.getLocationById(primaryLocationId, true)
      : skipToken,
  });
