import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../services/api';
import type { LocationsResponse } from '../types/locations';
import type { MetricsFilters } from '../types/metrics';

export const useLocations = (filters?: MetricsFilters) =>
  useQuery<LocationsResponse>({
    queryKey: ['locations', filters],
    queryFn: () => {
      if (!filters || !filters.table || !filters.configuration || !filters.variable) {
        throw new Error(
          'table, configuration, and variable filters are required to fetch locations'
        );
      }
      return apiService.getMetrics(filters);
    },
    enabled: !!filters && !!filters.table && !!filters.configuration && !!filters.variable,
  });
