import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

export const useDistinctValues = (
  table: string,
  columnName: string,
  filters?: Record<string, string>
) =>
  useQuery({
    queryKey: ['distinctValues', table, columnName, filters],
    queryFn: () => apiService.getDistinctValues(table, columnName, filters),
  });
