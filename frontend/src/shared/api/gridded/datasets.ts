import type { DatasetsResponse } from '@/shared/types/gridded/datasets';

import { griddedApiCall } from './client';

export const getGriddedDatasets = () => griddedApiCall<DatasetsResponse>('/api/dataset-keys');
