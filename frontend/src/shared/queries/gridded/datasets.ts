import { useQuery } from '@tanstack/react-query';
import { griddedApiService } from '../../../services/griddedApi';

export const useDatasets = () => {
  const query = useQuery({
    queryKey: ['gridded', 'datasets'],
    queryFn: () => griddedApiService.getGriddedDatasets(),
    select: (data) => data?.datasets ?? [],
  });

  return { ...query, data: query.data ?? [] };
};
