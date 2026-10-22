import { queryOptions, useQuery } from '@tanstack/react-query';

import { getAttributes, type AttributesResponse } from '@/shared/api/attributes';

export const attributesOptions = queryOptions<AttributesResponse>({
  queryKey: ['attributes'],
  queryFn: () => getAttributes(),
});

export const useAttributes = () => useQuery(attributesOptions);
