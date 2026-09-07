import { useQuery } from '@tanstack/react-query';

import apiService from '@/services/api';

import type { ConfigurationsTableResponse } from '../types/configurations';

export const useConfigurationsLocationsGeoJson = (configuration?: string, variable?: string) =>
  useQuery({
    queryKey: ['configurationsLocationsGeoJson', configuration, variable],
    queryFn: () =>
      apiService.getConfigurationLocationsGeojson({
        configuration_name: configuration,
        variable_name: variable,
      }),
    enabled: !!configuration && !!variable,
  });

export const useConfigurationsTable = () =>
  useQuery({
    queryKey: ['configurationsTable'],
    queryFn: () => apiService.getConfigurationsTable(),
    select: (data: ConfigurationsTableResponse) => data.items,
  });
