import { useQuery } from '@tanstack/react-query';

import { getGriddedDatasets } from '../../../services/griddedApi';

export const useDatasets = () => {
  const query = useQuery({
    queryKey: ['gridded', 'datasets'],
    queryFn: () => getGriddedDatasets(),
    select: (data) => data?.datasets ?? [],
  });

  return { ...query, data: query.data ?? [] };
};
