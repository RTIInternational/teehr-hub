import type { OgcResponse } from '@/shared/types/ogc';

export type ConfigurationCompletenessItem = {
  spatial_aggregate: string;
  period: string;
  actual_count: number;
  expected_count: number;
  completeness: number;
  configuration_name: string;
  variable_name: string;
};

export type ConfigurationCompletenessResponse = OgcResponse<ConfigurationCompletenessItem>;
