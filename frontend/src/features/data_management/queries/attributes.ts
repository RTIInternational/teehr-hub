import { queryOptions, useQuery } from '@tanstack/react-query';

import { getAttributes } from '@/shared/api/attributes';

import type { AttributesResponse } from '../types/attributes';

export const attributesOptions = queryOptions<AttributesResponse>({
  queryKey: ['attributes'],
  queryFn: () => getAttributes(),
});

export const useAttributes = () => useQuery(attributesOptions);
