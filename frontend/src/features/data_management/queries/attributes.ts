import { queryOptions, useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

import type { AttributesResponse } from '../types/attributes';

export const attributesOptions = queryOptions<AttributesResponse>({
  queryKey: ['attributes'],
  queryFn: () => apiService.getAttributes(),
});

export const useAttributes = () => useQuery(attributesOptions);
