import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

export const useDistinctValues = (table: string, column: string) =>
  useQuery<string[]>({
    queryKey: ['distinctValues', table, column],
    queryFn: () => apiService.getDistinctValues(table, column),
    enabled: !!table && !!column,
  });
