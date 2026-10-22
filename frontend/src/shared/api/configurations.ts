import { apiCallJson } from '@/shared/api/client';
import type { OgcResponse } from '@/shared/api/ogc';

export type ConfigurationsTableItem = {
  [property: string]: unknown;
  configuration_name: string;
  variable_name: string;
};

export type ConfigurationsTableResponse = OgcResponse<ConfigurationsTableItem>;

export type ConfigurationsSummaryItem = {
  configuration_name: string;
  variable_name: string;
  unit_name: string;
  min_reference_time: string;
  max_reference_time: string;
  min_value_time: string;
  max_value_time: string;
  n_locations: number;
  description: string;
  timeseries_type: string;
  location_id_prefix: string;
  created_at: string;
  updated_at: string;
};

export type ConfigurationsSummaryResponse = OgcResponse<ConfigurationsSummaryItem>;

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
