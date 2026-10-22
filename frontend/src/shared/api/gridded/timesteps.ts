import type { TimestepsResponse } from '@/shared/types/gridded/timesteps';

import { griddedApiCall } from './client';

export const getGriddedTimesteps = (datasetId: string) =>
  griddedApiCall<TimestepsResponse>(`/api/datasets/${encodeURIComponent(datasetId)}/coords/time`);
