import { griddedApiCall } from './client';

export type TimestepsResponse = {
  dataset_id: string;
  coord_name: string;
  values: string[];
};

export const getGriddedTimesteps = (datasetId: string) =>
  griddedApiCall<TimestepsResponse>(`/api/datasets/${encodeURIComponent(datasetId)}/coords/time`);
