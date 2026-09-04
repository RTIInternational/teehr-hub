import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

import type { LocationMetadataResponse, LocationsResponse } from '../types/locations';
import type { MetricsFilters } from '../types/metrics';

export const useLocationMetadata = (primaryLocationId?: string | null) =>
  useQuery<LocationMetadataResponse>({
    queryKey: ['locationMetadata', primaryLocationId],
    queryFn: () => apiService.getLocationById(primaryLocationId, true),
    enabled: !!primaryLocationId,
  });

export const useLocations = (filters?: MetricsFilters) =>
  useQuery<LocationsResponse>({
    queryKey: ['locations', filters],
    queryFn: () => apiService.getMetrics(filters),
    enabled: !!filters,
  });
