import type { FeatureCollection, Point } from 'geojson';

import type { AttributesResponse } from '@/features/data_management/types/attributes';
import type { ConfigurationsTableResponse } from '@/features/data_management/types/configurations';
import type { LocationAttributesResponse } from '@/features/data_management/types/locationAttributes';
import { apiCallJson, apiCallVoid } from '@/shared/api/client';
import { aliasMap } from '@/shared/api/utils';
import type { ApiKeysResponse, CreateApiKeyResponse } from '@/shared/types/apiKeys';
import type { ConfigurationsSummaryResponse } from '@/shared/types/configurations';
import type { LocationMetadataResponse, LocationsResponse } from '@/shared/types/locations';
import type { OgcResponse } from '@/shared/types/ogc';
import type { QueryablesResponse } from '@/shared/types/queryables';

// Get all locations (OGC API - Features)
export const getLocations = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<OgcResponse<FeatureCollection>>(
    `/collections/locations/items?${params.toString()}`
  );
};

// Get queryables for a collection (OGC API - Features Part 3)
// Returns schema with x-teehr-role extensions for group_by/metric fields
export const getQueryables = (collection = 'sim_metrics_by_location') => {
  return apiCallJson<QueryablesResponse>(`/collections/${collection}/queryables`);
};

// Get distinct values for a queryable property (TEEHR extension)
export const getQueryableValues = (collection: string, propertyName: string) => {
  return apiCallJson<string[]>(`/collections/${collection}/queryables/${propertyName}/values`);
};

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

// Get variables (distinct variable_name values)
export const getVariables = async (table = 'sim_metrics_by_location') => {
  return apiCallJson<string[]>(`/collections/${table}/queryables/variable_name/values`);
};

// Get distinct values for requested column with optional filters
export const getDistinctValues = async (
  table = 'sim_metrics_by_location',
  columnName: string,
  filters?: Record<string, string>
) => {
  const params = new URLSearchParams();

  for (const key in filters) {
    const paramKey = aliasMap[key] || key;
    const filterValue = filters[key] === null ? 'null' : filters[key];
    if (filterValue) params.append(paramKey, filterValue);
  }

  const paramString = params.toString();
  const endpoint = paramString
    ? `/collections/${table}/queryables/${columnName}/values?${paramString}`
    : `/collections/${table}/queryables/${columnName}/values`;

  return apiCallJson<string[]>(endpoint);
};

// Get table properties (now via queryables endpoint)
export const getTableProperties = (table = 'sim_metrics_by_location') => {
  return apiCallJson(`/collections/${table}/queryables`);
};

// Get table properties for multiple tables in batch
export const getTablePropertiesBatch = async (tables = ['sim_metrics_by_location']) => {
  const results = await Promise.all(
    tables.map((table) => apiCallJson<QueryablesResponse>(`/collections/${table}/queryables`))
  );
  // Return as object keyed by table name
  return tables.reduce<Record<string, QueryablesResponse | null>>((acc, table, idx) => {
    acc[table] = results[idx];
    return acc;
  }, {});
};

// Get available collections (OGC API - Common)
export const getCollections = () => apiCallJson('/collections');

// Get landing page (OGC API - Common)
export const getLandingPage = () => apiCallJson('/');

// Get conformance (OGC API - Common)
export const getConformance = () => apiCallJson('/conformance');

// Health check
export const healthCheck = () => apiCallJson('/health');

// Auth info
export const getMe = () => apiCallJson('/auth/me');

// API key management (admin JWT required)
export const listApiKeys = () => apiCallJson<ApiKeysResponse>('/auth/api-keys');
export const createApiKey = (name: string, scopes: string[] = []) =>
  apiCallJson<CreateApiKeyResponse>('/auth/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, scopes }),
  });
export const revokeApiKey = (keyId: string) =>
  apiCallVoid(`/auth/api-keys/${encodeURIComponent(keyId)}`, {
    method: 'DELETE',
  });

// Get location id + name (no geometry) filtered by prefix, returns {items: [{id, name}]}
export const getLocationIdNames = (prefix: string, limit: number | null = null) => {
  const params = new URLSearchParams();
  if (prefix) params.append('prefix', prefix);
  params.append('include_geometry', 'false');
  if (limit != null) params.append('limit', limit.toString());
  return apiCallJson<LocationsResponse>(`/collections/locations/items?${params.toString()}`);
};

// Get attribute definitions (name, description, type, updated_at, etc.)
export const getAttributes = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<AttributesResponse>(`/collections/attributes/items?${params.toString()}`);
};

// Get location attributes for specified attribute names (EAV rows, one per location+name)
// Returns {items: [{location_id, attribute_name, value}, ...]}
export const getLocationAttributesByNames = (attributeNames: string[] = [], limit = null) => {
  const params = new URLSearchParams();
  attributeNames.forEach((name) => params.append('attribute_name', name));
  if (limit != null) params.append('limit', limit);
  return apiCallJson<LocationAttributesResponse>(
    `/collections/location_attributes/items?${params.toString()}`
  );
};

// Get a single location by id from the locations table
// Returns a GeoJSON FeatureCollection with the matching feature
export const getLocationById = (id: string, includeAttributes = false) => {
  const params = new URLSearchParams();
  params.append('id', id);
  params.append('limit', '1');
  params.append('include_attributes', includeAttributes.toString());
  return apiCallJson<LocationMetadataResponse>(`/collections/locations/items?${params.toString()}`);
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

// Get GeoJSON for all locations matching a configuration + variable
export const getConfigurationLocationsGeojson = (
  filters: { configuration_name?: string; variable_name?: string; limit?: number } = {}
) => {
  const params = new URLSearchParams();
  if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
  if (filters.variable_name) params.append('variable_name', filters.variable_name);
  params.append('f', 'geojson');
  params.append('limit', filters.limit?.toString() ?? '50000');
  return apiCallJson<FeatureCollection<Point>>(
    `/collections/configurations_by_location/items?${params.toString()}`
  );
};
