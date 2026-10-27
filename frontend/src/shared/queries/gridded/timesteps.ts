import { queryOptions, useQuery } from '@tanstack/react-query';

import { getGriddedTimesteps } from '@/shared/api/gridded/timesteps';

const fetchTimesteps = async (datasetId?: string | null) => {
  if (!datasetId) {
    throw new Error('Dataset required to retrieve timesteps');
  }

  return getGriddedTimesteps(datasetId);
};

export const timestepsQueryOptions = (datasetId?: string | null) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'timesteps'],
    queryFn: () => fetchTimesteps(datasetId),
    enabled: !!datasetId,
    select: (data) => data.values,
  });

export const useTimesteps = (datasetId?: string | null) => {
  const query = useQuery(timestepsQueryOptions(datasetId));
  return { ...query, data: query.data ?? [] };
};
