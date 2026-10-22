import { skipToken, useQuery } from '@tanstack/react-query';

import { getLocationById } from '@/shared/api/locations';

export const useLocationMetadata = (primaryLocationId?: string | null) =>
  useQuery({
    queryKey: ['locationMetadata', primaryLocationId],
    queryFn: primaryLocationId ? () => getLocationById(primaryLocationId, true) : skipToken,
  });
