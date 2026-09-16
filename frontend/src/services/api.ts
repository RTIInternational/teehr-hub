import type { MultiPolygon, FeatureCollection, Point, Polygon } from 'geojson';

import { ensureFreshToken, getKeycloak } from '@/features/auth';
import type { AttributesResponse } from '@/features/data_management/types/attributes';
import type { ConfigurationCompletenessResponse } from '@/features/data_management/types/completeness';
import type { ConfigurationsTableResponse } from '@/features/data_management/types/configurations';
import type { LocationAttributesResponse } from '@/features/data_management/types/locationAttributes';
import type { ApiKeysResponse, CreateApiKeyResponse } from '@/shared/types/apiKeys';
import type { CompletenessRequestFilters } from '@/shared/types/completeness';
import type { ConfigurationsSummaryResponse } from '@/shared/types/configurations';
import type { LocationMetadataResponse, LocationsResponse } from '@/shared/types/locations';
import type { MetricsFilters } from '@/shared/types/metrics';
import type { OgcResponse } from '@/shared/types/ogc';
import type { QueryablesResponse } from '@/shared/types/queryables';
import {
  type PrimaryTimeseriesRequestFilters,
  type SecondaryTimeseriesRequestFilters,
  type TimeseriesResponse,
} from '@/shared/types/timeseries';
import {
  groupPrimaryTimeseriesItems,
  groupSecondaryTimeseriesItems,
} from '@/shared/utils/timeseries';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = import.meta.env.VITE_API_KEY || '';

const normalizeEndpoint = (endpoint: string) => {
  if (!endpoint) return endpoint;
  if (endpoint.startsWith('http://') || endpoint.startsWith('https://')) {
    const parsed = new URL(endpoint);
    return `${parsed.pathname}${parsed.search}`;
  }
  return endpoint;
};

const normalizeHeaders = (headers?: HeadersInit): Record<string, string> => {
  if (!headers) return {};
  if (headers instanceof Headers) {
    return Object.fromEntries(headers);
  }
  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }
  return headers as Record<string, string>;
};

// Helper function for API calls
const apiCallJson = async <T>(endpoint: string, options: RequestInit = {}): Promise<T> => {
  try {
    const normalizedEndpoint = normalizeEndpoint(endpoint);
    const url = `${API_BASE_URL}${normalizedEndpoint}`;
    const refreshedToken = await ensureFreshToken();
    const token = refreshedToken || getKeycloak().token || null;
    const { headers: extraHeaders = {}, ...restOptions } = options;
    const authHeaders = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && API_KEY ? { 'X-API-Key': API_KEY } : {}),
    };

    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
        ...authHeaders,
        ...normalizeHeaders(extraHeaders),
      },
      ...restOptions,
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody?.detail ? ` - ${errorBody.detail}` : '';
      } catch {
        detail = '';
      }
      throw new Error(`API Error: ${response.status} ${response.statusText}${detail}`);
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('json')) {
      throw new Error(`Expected JSON response, got ${contentType || 'unknown content-type'}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

const apiCallVoid = async (endpoint: string, options: RequestInit = {}): Promise<void> => {
  try {
    const normalizedEndpoint = normalizeEndpoint(endpoint);
    const url = `${API_BASE_URL}${normalizedEndpoint}`;
    const refreshedToken = await ensureFreshToken();
    const token = refreshedToken || getKeycloak().token || null;
    const { headers: extraHeaders = {}, ...restOptions } = options;
    const authHeaders = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && API_KEY ? { 'X-API-Key': API_KEY } : {}),
    };

    const response = await fetch(url, {
      headers: {
        ...authHeaders,
        ...normalizeHeaders(extraHeaders),
      },
      ...restOptions,
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody?.detail ? ` - ${errorBody.detail}` : '';
      } catch {
        detail = '';
      }
      throw new Error(`API Error: ${response.status} ${response.statusText}${detail}`);
    }
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

// Helper to format ISO 8601 datetime interval
const formatDatetimeInterval = (startDate?: string, endDate?: string) => {
  if (!startDate && !endDate) return null;
  const start = startDate || '..';
  const end = endDate || '..';
  return `${start}/${end}`;
};

// API service object - OGC API compliant
export const apiService = {
  // Get all locations (OGC API - Features)
  getLocations: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    return apiCallJson<OgcResponse<FeatureCollection>>(
      `/collections/locations/items?${params.toString()}`
    );
  },

  // Get queryables for a collection (OGC API - Features Part 3)
  // Returns schema with x-teehr-role extensions for group_by/metric fields
  getQueryables: (collection = 'sim_metrics_by_location') => {
    return apiCallJson<QueryablesResponse>(`/collections/${collection}/queryables`);
  },

  // Get distinct values for a queryable property (TEEHR extension)
  getQueryableValues: (collection: string, propertyName: string) => {
    return apiCallJson<string[]>(`/collections/${collection}/queryables/${propertyName}/values`);
  },

  // Get configurations (distinct configuration_name values)
  getConfigurations: async (table = 'sim_metrics_by_location') => {
    return apiCallJson<string[]>(`/collections/${table}/queryables/configuration_name/values`);
  },

  // Get configurations summary rows from iceberg.teehr.configurations_summary
  getConfigurationsTable: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    return apiCallJson<ConfigurationsSummaryResponse>(
      `/collections/configurations_summary/items?${params.toString()}`
    );
  },

  // Get variables (distinct variable_name values)
  getVariables: async (table = 'sim_metrics_by_location') => {
    return apiCallJson<string[]>(`/collections/${table}/queryables/variable_name/values`);
  },

  // Get distinct values for requested column
  getDistinctValues: async (table = 'sim_metrics_by_location', columnName: string) => {
    return apiCallJson<string[]>(`/collections/${table}/queryables/${columnName}/values`);
  },

  // Get table properties (now via queryables endpoint)
  getTableProperties: (table = 'sim_metrics_by_location') => {
    return apiCallJson(`/collections/${table}/queryables`);
  },

  // Get table properties for multiple tables in batch
  getTablePropertiesBatch: async (tables = ['sim_metrics_by_location']) => {
    const results = await Promise.all(
      tables.map((table) => apiCallJson<QueryablesResponse>(`/collections/${table}/queryables`))
    );
    // Return as object keyed by table name
    return tables.reduce<Record<string, QueryablesResponse | null>>((acc, table, idx) => {
      acc[table] = results[idx];
      return acc;
    }, {});
  },

  // Get metrics with filtering (OGC API - Features)
  getMetrics: (filters: Partial<MetricsFilters> = {}) => {
    const params = new URLSearchParams();
    const table = filters.table || 'sim_metrics_by_location';

    const reservedKeys = ['table'];

    const aliasMap: Record<string, string> = {
      waterYear: 'water_year',
      aggMethod: 'window_agg',
      configuration: 'configuration_name',
      leadTimeBin: 'forecast_lead_time_bin',
      primary_location_id: 'location_id',
      variable: 'variable_name',
    };

    for (const key in filters) {
      if (reservedKeys.includes(key)) continue;
      const paramKey = aliasMap[key] || key;
      const filterValue = filters[key] === null ? 'null' : filters[key];
      if (filterValue) params.append(paramKey, filterValue);
    }

    const queryString = params.toString();
    const endpoint = queryString
      ? `/collections/${table}/items?${queryString}`
      : `/collections/${table}/items`;

    return apiCallJson<FeatureCollection<Point>>(endpoint);
  },

  // Get primary timeseries (simple JSON array format)
  getPrimaryTimeseries: async (
    primaryLocationId: string,
    filters: PrimaryTimeseriesRequestFilters = {}
  ) => {
    const params = new URLSearchParams();
    params.append('primary_location_id', primaryLocationId);

    // Use ISO 8601 datetime interval
    const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
    if (datetime) params.append('datetime', datetime);

    if (Array.isArray(filters.variable)) {
      filters.variable.forEach((variable) => {
        if (variable) params.append('variable_name', variable);
      });
    } else if (filters.variable) {
      params.append('variable_name', filters.variable);
    }

    if (Array.isArray(filters.configuration)) {
      filters.configuration.forEach((configuration) => {
        if (configuration) params.append('configuration_name', configuration);
      });
    } else if (filters.configuration) {
      params.append('configuration_name', filters.configuration);
    }
    if (filters.duration) params.append('timestep_duration', filters.duration);

    params.append('f', 'json');
    if (Number.isFinite(filters.limit)) {
      params.append('limit', Math.max(1, Number(filters.limit)).toString());
    }

    let nextEndpoint: string | null = `/collections/primary_timeseries/items?${params.toString()}`;
    const allItems = [];

    while (nextEndpoint) {
      const response: TimeseriesResponse | null =
        await apiCallJson<TimeseriesResponse>(nextEndpoint);
      const pageItems = Array.isArray(response?.items) ? response.items : [];
      allItems.push(...pageItems);

      const nextHref: string | undefined = response?.links?.find(
        (link) => link.rel === 'next'
      )?.href;
      nextEndpoint = nextHref ? normalizeEndpoint(nextHref) : null;
    }

    return groupPrimaryTimeseriesItems(allItems);
  },

  // Get secondary timeseries (simple JSON array format)
  getSecondaryTimeseries: async (
    primaryLocationId: string,
    filters: SecondaryTimeseriesRequestFilters = {}
  ) => {
    const params = new URLSearchParams();
    params.append('primary_location_id', primaryLocationId);

    // Use ISO 8601 datetime interval for value_time
    const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
    if (datetime) params.append('datetime', datetime);

    // Use ISO 8601 datetime interval for reference_time
    const refDatetime = formatDatetimeInterval(
      filters.reference_start_date,
      filters.reference_end_date
    );
    if (refDatetime) params.append('reference_time', refDatetime);

    if (Array.isArray(filters.configuration)) {
      filters.configuration.forEach((configuration) => {
        if (configuration) params.append('configuration_name', configuration);
      });
    } else if (filters.configuration) {
      params.append('configuration_name', filters.configuration);
    }

    if (Array.isArray(filters.variable)) {
      filters.variable.forEach((variable) => {
        if (variable) params.append('variable_name', variable);
      });
    } else if (filters.variable) {
      params.append('variable_name', filters.variable);
    }
    if (filters.duration) params.append('timestep_duration', filters.duration);

    // Use paged JSON retrieval so we can follow next links and fetch all rows,
    // then regroup into the historical timeseries response shape expected by the UI.
    params.append('f', 'json');
    if (Number.isFinite(filters.limit)) {
      params.append('limit', Math.max(1, Number(filters.limit)).toString());
    }

    let nextEndpoint: string | null =
      `/collections/secondary_timeseries/items?${params.toString()}`;
    const allItems = [];

    while (nextEndpoint) {
      const response: TimeseriesResponse | null =
        await apiCallJson<TimeseriesResponse>(nextEndpoint);
      const pageItems = Array.isArray(response?.items) ? response.items : [];
      allItems.push(...pageItems);

      const nextHref: string | undefined = response?.links?.find(
        (link) => link.rel === 'next'
      )?.href;
      nextEndpoint = nextHref ? normalizeEndpoint(nextHref) : null;
    }
    const groupedSecondaryItems = groupSecondaryTimeseriesItems(allItems);
    return groupedSecondaryItems;
  },

  // Get available collections (OGC API - Common)
  getCollections: () => apiCallJson('/collections'),

  // Get landing page (OGC API - Common)
  getLandingPage: () => apiCallJson('/'),

  // Get conformance (OGC API - Common)
  getConformance: () => apiCallJson('/conformance'),

  // Health check
  healthCheck: () => apiCallJson('/health'),

  // Auth info
  getMe: () => apiCallJson('/auth/me'),

  // API key management (admin JWT required)
  listApiKeys: () => apiCallJson<ApiKeysResponse>('/auth/api-keys'),
  createApiKey: (name: string, scopes: string[] = []) =>
    apiCallJson<CreateApiKeyResponse>('/auth/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, scopes }),
    }),
  revokeApiKey: (keyId: string) =>
    apiCallVoid(`/auth/api-keys/${encodeURIComponent(keyId)}`, {
      method: 'DELETE',
    }),

  // Get locations filtered by ID prefix, returns GeoJSON FeatureCollection
  getLocationsByPrefix: (prefix: string, limit = 5000) => {
    const params = new URLSearchParams();
    params.append('prefix', prefix);
    params.append('limit', limit.toString());
    return apiCallJson<FeatureCollection<Polygon | MultiPolygon>>(
      `/collections/locations/items?${params.toString()}`
    );
  },

  // Get location id + name (no geometry) filtered by prefix, returns {items: [{id, name}]}
  getLocationIdNames: (prefix: string, limit: number | null = null) => {
    const params = new URLSearchParams();
    if (prefix) params.append('prefix', prefix);
    params.append('include_geometry', 'false');
    if (limit != null) params.append('limit', limit.toString());
    return apiCallJson<LocationsResponse>(`/collections/locations/items?${params.toString()}`);
  },

  // Get attribute definitions (name, description, type, updated_at, etc.)
  getAttributes: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    return apiCallJson<AttributesResponse>(`/collections/attributes/items?${params.toString()}`);
  },

  // Get configuration completeness heatmap data
  getCompletenessHeatmap: (filters: CompletenessRequestFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    if (filters.limit) params.append('limit', filters.limit.toString());
    if (filters.offset) params.append('offset', filters.offset.toString());
    return apiCallJson<ConfigurationCompletenessResponse>(
      `/collections/configuration_completeness/items?${params.toString()}`
    );
  },

  // Get location attributes for specified attribute names (EAV rows, one per location+name)
  // Returns {items: [{location_id, attribute_name, value}, ...]}
  getLocationAttributesByNames: (attributeNames: string[] = [], limit = null) => {
    const params = new URLSearchParams();
    attributeNames.forEach((name) => params.append('attribute_name', name));
    if (limit != null) params.append('limit', limit);
    return apiCallJson<LocationAttributesResponse>(
      `/collections/location_attributes/items?${params.toString()}`
    );
  },

  // Get a single location by id from the locations table
  // Returns a GeoJSON FeatureCollection with the matching feature
  getLocationById: (id: string, includeAttributes = false) => {
    const params = new URLSearchParams();
    params.append('id', id);
    params.append('limit', '1');
    params.append('include_attributes', includeAttributes.toString());
    return apiCallJson<LocationMetadataResponse>(
      `/collections/locations/items?${params.toString()}`
    );
  },

  // Get configurations_by_location rows for a specific location_id (all rows for that location)
  getConfigurationsByLocationId: (locationId: string) => {
    const params = new URLSearchParams();
    params.append('location_id', locationId);
    return apiCallJson<ConfigurationsTableResponse>(
      `/collections/configurations_by_location/expanded?${params.toString()}`
    );
  },

  // Get GeoJSON for all locations matching a configuration + variable via a backend JOIN (no URL-length limit)
  getConfigurationLocationsGeojson: (
    filters: { configuration_name?: string; variable_name?: string } = {}
  ) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    return apiCallJson<FeatureCollection<Point>>(
      `/collections/configurations_by_location/locations-geojson?${params.toString()}`
    );
  },
};

export default apiService;
