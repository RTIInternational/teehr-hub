import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../services/api';
import type { LocationsResponse } from '../types/locations';
import type { MetricsFilters } from '../types/metrics';

export const useLocations = (filters?: MetricsFilters) =>
  useQuery<LocationsResponse>({
    queryKey: ['locations', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: !!filters,
  });
