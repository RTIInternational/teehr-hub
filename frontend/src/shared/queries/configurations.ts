import { useQuery } from '@tanstack/react-query';

import { getConfigurations } from '@/shared/api/configurations';

export const useConfigurations = (table: string) =>
  useQuery({
    queryKey: ['configurations', table],
    queryFn: () => getConfigurations(table),
  });
