import { skipToken, useQuery } from '@tanstack/react-query';

import { getConfigurationsByLocationId, getConfigurationsTable } from '@/shared/api/configurations';
import { getConfigurationLocationsGeojson } from '@/shared/api/locations';

import type { ConfigurationsTableResponse } from '../types/configurations';

export const useConfigurationsByLocationId = (locationId: string | null) =>
  useQuery({
    queryKey: ['configurationsByLocationId', locationId],
    queryFn: locationId ? () => getConfigurationsByLocationId(locationId) : skipToken,
    select: (data: ConfigurationsTableResponse) => data.items,
  });

export const useConfigurationsLocationsGeoJson = (configuration?: string, variable?: string) =>
  useQuery({
    queryKey: ['configurationsLocationsGeoJson', configuration, variable],
    queryFn: () =>
      getConfigurationLocationsGeojson({
        configuration_name: configuration,
        variable_name: variable,
      }),
    enabled: !!configuration && !!variable,
  });

export const useConfigurationsTable = () =>
  useQuery({
    queryKey: ['configurationsTable'],
    queryFn: () => getConfigurationsTable(),
    select: (data: ConfigurationsTableResponse) => data.items,
  });
