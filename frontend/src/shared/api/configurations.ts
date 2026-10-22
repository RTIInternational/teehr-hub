import type { ConfigurationsTableResponse } from '@/features/data_management/types/configurations';
import { apiCallJson } from '@/shared/api/client';
import type { ConfigurationsSummaryResponse } from '@/shared/types/configurations';

// Get configurations (distinct configuration_name values)
export const getConfigurations = async (table = 'sim_metrics_by_location') => {
  return apiCallJson<string[]>(`/collections/${table}/queryables/configuration_name/values`);
};

// Get configurations summary rows from iceberg.teehr.configurations_summary
export const getConfigurationsTable = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<ConfigurationsSummaryResponse>(
    `/collections/configurations_summary/items?${params.toString()}`
  );
};

// Get configurations_by_location rows for a specific location_id (all rows for that location)
// f=json skips the GeoJSON encoding and the geometry column, which this table view does not need
export const getConfigurationsByLocationId = (locationId: string) => {
  const params = new URLSearchParams();
  params.append('location_id', locationId);
  params.append('f', 'json');
  return apiCallJson<ConfigurationsTableResponse>(
    `/collections/configurations_by_location/items?${params.toString()}`
  );
};
