import type { OgcResponse } from '@/shared/types/ogc';

type ConfigurationTableItem = {
  [property: string]: unknown;
};

export type ConfigurationsTableResponse = OgcResponse<ConfigurationTableItem>;
