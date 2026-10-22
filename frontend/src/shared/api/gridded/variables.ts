import type { VariablesResponse } from '@/shared/types/gridded/variables';

import { griddedApiCall } from './client';

export const getGriddedVariables = (datasetId: string) =>
  griddedApiCall<VariablesResponse>(`/api/dataset-variables/${encodeURIComponent(datasetId)}`);
