import { griddedApiCall } from './client';

export type CoordValuesResponse = {
  dataset_id: string;
  coord_name: string;
  values: string[];
};

// A coordinate's values, without time-grid slots that hold no data
export const getGriddedCoordValues = (datasetId: string, coordName: string) =>
  griddedApiCall<CoordValuesResponse>(
    `/api/datasets/${encodeURIComponent(datasetId)}/coords/${encodeURIComponent(coordName)}`
  );
