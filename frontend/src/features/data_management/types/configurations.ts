import type { OgcResponse } from '@/shared/types/ogc';

export type ConfigurationsTableItem = {
  [property: string]: unknown;
  configuration_name: string;
  variable_name: string;
};

export type ConfigurationsTableResponse = OgcResponse<ConfigurationsTableItem>;
