import { griddedApiCall } from './client';

export type DatasetsResponse = {
  datasets: string[];
};

export const getGriddedDatasets = () => griddedApiCall<DatasetsResponse>('/api/dataset-keys');
