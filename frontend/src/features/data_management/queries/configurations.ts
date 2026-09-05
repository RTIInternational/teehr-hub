import { useQuery } from '@tanstack/react-query';

import apiService from '@/services/api';

import type { ConfigurationsTableResponse } from '../types/configurations';

export const useConfigurationsTable = () =>
  useQuery({
    queryKey: ['configurationsTable'],
    queryFn: () => apiService.getConfigurationsTable(),
    select: (data: ConfigurationsTableResponse) => data.items,
  });
