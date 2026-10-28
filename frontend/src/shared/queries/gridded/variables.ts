import { queryOptions, useQuery } from '@tanstack/react-query';

import { getGriddedVariables } from '@/shared/api/gridded/variables';

const fetchVariables = async (datasetId?: string | null) => {
  if (!datasetId) {
    throw new Error('Dataset required to retrieve variables');
  }

  return getGriddedVariables(datasetId);
};

export const variablesQueryOptions = (datasetId?: string | null) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'variables'],
    queryFn: () => fetchVariables(datasetId),
    enabled: !!datasetId,
    select: (data) => data.variables,
  });

export const useVariables = (datasetId?: string | null) => {
  const query = useQuery(variablesQueryOptions(datasetId));
  return { ...query, data: query.data ?? [] };
};
