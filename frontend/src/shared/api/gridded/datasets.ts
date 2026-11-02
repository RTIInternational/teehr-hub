import { griddedApiCall } from './client';

export type DatasetsResponse = {
  datasets: string[];
};

// A dataset's shape: its append axis (time, or reference_time for forecasts) and the forecast
// axes after it, e.g. ['lead_time'] or ['member', 'lead_time']; empty for analysis datasets
export type GridSpec = {
  dataset_id: string;
  append_dim: string;
  fixed_dims: string[];
  layout_version: number;
};

export const getGriddedDatasets = () => griddedApiCall<DatasetsResponse>('/api/dataset-keys');

export const getGriddedGridSpec = (datasetId: string) =>
  griddedApiCall<GridSpec>(`/api/datasets/${encodeURIComponent(datasetId)}/grid-spec`);
