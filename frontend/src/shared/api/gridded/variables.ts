import { griddedApiCall } from './client';

export type VariablesResponse = {
  dataset_id: string;
  variables: string[];
};

export const getGriddedVariables = (datasetId: string) =>
  griddedApiCall<VariablesResponse>(`/api/dataset-variables/${encodeURIComponent(datasetId)}`);
