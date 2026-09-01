import { useQuery } from '@tanstack/react-query';
import { apiService } from '@/services/api';

export const useVariables = (table: string) =>
  useQuery<string[]>({
    queryKey: ['variables', table],
    queryFn: () => apiService.getVariables(table),
  });
