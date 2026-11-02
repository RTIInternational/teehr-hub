import { queryOptions, useQuery, type QueryClient } from '@tanstack/react-query';

import { getGriddedCoordValues } from '@/shared/api/gridded/timesteps';

import { metadataQueryOptions } from './datasets';

// Steps along the dataset's append axis: valid times, or a forecast's cycles. The axis comes from
// the dataset's metadata, through the query cache.
const fetchTimesteps = async (client: QueryClient, datasetId?: string | null) => {
  if (!datasetId) {
    throw new Error('Dataset required to retrieve timesteps');
  }
  const metadata = await client.ensureQueryData(metadataQueryOptions(datasetId));
  return getGriddedCoordValues(datasetId, metadata.append_dim);
};

export const timestepsQueryOptions = (datasetId?: string | null) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'timesteps'],
    queryFn: ({ client }) => fetchTimesteps(client, datasetId),
    enabled: !!datasetId,
    select: (data) => data.values,
  });

export const useTimesteps = (datasetId?: string | null) => {
  const query = useQuery(timestepsQueryOptions(datasetId));
  return { ...query, data: query.data ?? [] };
};

export const coordValuesQueryOptions = (datasetId: string | null | undefined, coordName: string) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'coords', coordName],
    queryFn: () => getGriddedCoordValues(datasetId!, coordName),
    enabled: !!datasetId,
    select: (data) => data.values,
  });
