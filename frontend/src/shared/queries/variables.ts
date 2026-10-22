import { useQuery } from '@tanstack/react-query';

import { getVariables } from '@/shared/api/variables';

export const useVariables = (table: string) =>
  useQuery({
    queryKey: ['variables', table],
    queryFn: () => getVariables(table),
  });
