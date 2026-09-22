import type { OgcResponse } from './ogc';

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
