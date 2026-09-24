import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

export const useDistinctValues = (table: string, columnName: string) =>
  useQuery({
    queryKey: ['distinctValues', table, columnName],
    queryFn: () => apiService.getDistinctValues(table, columnName),
  });
