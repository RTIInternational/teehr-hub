import { queryOptions, useQuery } from '@tanstack/react-query';

import { getGriddedDatasets, getGriddedGridSpec } from '@/shared/api/gridded/datasets';

export const useDatasets = () => {
  const query = useQuery({
    queryKey: ['gridded', 'datasets'],
    queryFn: () => getGriddedDatasets(),
    select: (data) => data?.datasets ?? [],
  });

  return { ...query, data: query.data ?? [] };
};

export const gridSpecQueryOptions = (datasetId?: string | null) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'gridSpec'],
    queryFn: () => getGriddedGridSpec(datasetId!),
    enabled: !!datasetId,
  });

export const useGridSpec = (datasetId?: string | null) => useQuery(gridSpecQueryOptions(datasetId));

// Whether a dataset is a forecast (has axes after its cycles); undefined until its spec loads
export const isForecast = (spec?: { fixed_dims: string[] }) =>
  spec === undefined ? undefined : spec.fixed_dims.length > 0;
