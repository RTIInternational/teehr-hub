import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../services/api';

export const useConfigurations = (table: string) =>
  useQuery<string[]>({
    queryKey: ['configurations', table],
    queryFn: () => apiService.getConfigurations(table),
  });
