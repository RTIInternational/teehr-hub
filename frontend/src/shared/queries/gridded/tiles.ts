import { useQuery } from '@tanstack/react-query';

import { griddedApiService } from '@/services/griddedApi';

export const usePolygonLayers = () =>
  useQuery({
    queryKey: ['polygons'],
    queryFn: () => griddedApiService.discoverPolygonLayers(),
    select: (data) => data.items,
  });
