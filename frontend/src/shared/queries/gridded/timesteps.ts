import { useQuery } from '@tanstack/react-query';
import { griddedApiService } from '../../../services/griddedApi';

const fetchTimesteps = async (datasetId?: string | null) => {
  if (!datasetId) {
    throw new Error('Dataset required to retrieve timesteps');
  }

  return griddedApiService.getGriddedTimesteps(datasetId);
};

export const useTimesteps = (datasetId?: string | null) => {
  const query = useQuery({
    queryKey: ['gridded', datasetId, 'timesteps'],
    queryFn: () => fetchTimesteps(datasetId),
    enabled: !!datasetId,
    select: (data) => data.values,
  });
  return { ...query, data: query.data ?? [] };
};
