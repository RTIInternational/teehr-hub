import { griddedApiCall } from './client';
import { getGriddedGridSpec } from './datasets';

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

// Steps along the dataset's append axis: valid times, or a forecast's cycles
export const getGriddedTimesteps = async (datasetId: string) => {
  const spec = await getGriddedGridSpec(datasetId);
  return getGriddedCoordValues(datasetId, spec.append_dim);
};
