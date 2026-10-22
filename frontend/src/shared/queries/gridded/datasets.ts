import { useQuery } from '@tanstack/react-query';

import { getGriddedDatasets } from '@/shared/api/gridded/datasets';

export const useDatasets = () => {
  const query = useQuery({
    queryKey: ['gridded', 'datasets'],
    queryFn: () => getGriddedDatasets(),
    select: (data) => data?.datasets ?? [],
  });

  return { ...query, data: query.data ?? [] };
};
