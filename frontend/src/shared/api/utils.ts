export const aliasMap: Record<string, string> = {
  waterYear: 'water_year',
  aggMethod: 'window_agg',
  configuration: 'secondary_configuration_name',
  leadTimeBin: 'forecast_lead_time_bin',
  primary_location_id: 'location_id',
  variable: 'secondary_variable_name',
};

export type TableProperties = {
  metrics: string[];
  group_by: string[];
  description: string;
  allProperties: string[];
};

export const normalizeEndpoint = (endpoint: string) => {
  if (!endpoint) return endpoint;
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    const parsed = new URL(endpoint);
    return `${parsed.pathname}${parsed.search}`;
  }
  return endpoint;
};

export const normalizeHeaders = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) return {};
  if (headers instanceof Headers) {
    return Object.fromEntries(headers);
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers as Record<string, string>;
};
