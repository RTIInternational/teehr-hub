import { queryOptions, useQuery } from '@tanstack/react-query';

import {
  getGriddedDatasets,
  getGriddedMetadata,
  type DatasetMetadata,
} from '@/shared/api/gridded/datasets';

export const useDatasets = () => {
  const query = useQuery({
    queryKey: ['gridded', 'datasets'],
    queryFn: () => getGriddedDatasets(),
    select: (data) => data?.datasets ?? [],
  });

  return { ...query, data: query.data ?? [] };
};

// A failed metadata request leaves the dataset treated as analysis data (one time axis), as every
// dataset was before the endpoint existed, so it never hides a dataset
const asAnalysis = (datasetId: string): DatasetMetadata => ({
  dataset_id: datasetId,
  append_dim: 'time',
  fixed_dims: [],
  layout_version: 1,
});

export const metadataQueryOptions = (datasetId?: string | null) =>
  queryOptions({
    queryKey: ['gridded', datasetId, 'metadata'],
    queryFn: () =>
      getGriddedMetadata(datasetId!).catch((error: unknown) => {
        console.warn(
          `Gridded metadata for '${datasetId}' unavailable; treating it as analysis data.`,
          error
        );
        return asAnalysis(datasetId!);
      }),
    enabled: !!datasetId,
  });

export const useDatasetMetadata = (datasetId?: string | null) =>
  useQuery(metadataQueryOptions(datasetId));

// Whether a dataset is a forecast (has axes after its cycles); undefined until its metadata loads
export const isForecast = (metadata?: { fixed_dims: string[] }) =>
  metadata === undefined ? undefined : metadata.fixed_dims.length > 0;
