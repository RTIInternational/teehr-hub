import type { VariableAttrsResponse } from '@/shared/types/gridded/variableAttrs';

import { griddedApiCall } from './client';

export const getGriddedVariableAttrs = (datasetId: string) =>
  griddedApiCall<VariableAttrsResponse>(
    `/api/datasets/${encodeURIComponent(datasetId)}/variable-attrs`
  );
