// API configuration - OGC-compliant endpoints
import { ensureFreshToken, getKeycloak } from '../auth/keycloak';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = import.meta.env.VITE_API_KEY || '';

// Helper function for API calls
const apiCall = async (endpoint, options = {}) => {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const refreshedToken = await ensureFreshToken();
    const token = refreshedToken || getKeycloak().token || null;
    const { headers: extraHeaders = {}, ...restOptions } = options;
    const authHeaders = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && API_KEY ? { 'X-API-Key': API_KEY } : {}),
    };

    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        ...authHeaders,
        ...extraHeaders,
      },
      ...restOptions,
    });

    if (response.status === 204) {
      return null;
    }

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
      return null;
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

// Helper to format ISO 8601 datetime interval
const formatDatetimeInterval = (startDate, endDate) => {
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
    params.append('limit', limit);
    params.append('offset', offset);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get queryables for a collection (OGC API - Features Part 3)
  // Returns schema with x-teehr-role extensions for group_by/metric fields
  getQueryables: (collection = 'sim_metrics_by_location') => {
    return apiCall(`/collections/${collection}/queryables`);
  },

  // Get distinct values for a queryable property (TEEHR extension)
  getQueryableValues: (collection, propertyName) => {
    return apiCall(`/collections/${collection}/queryables/${propertyName}/values`);
  },

  // Get configurations (distinct configuration_name values)
  getConfigurations: async (table = 'sim_metrics_by_location') => {
    return apiCall(`/collections/${table}/queryables/configuration_name/values`);
  },

  // Get configurations summary rows from iceberg.teehr.configurations_summary
  getConfigurationsTable: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit);
    params.append('offset', offset);
    return apiCall(`/collections/configurations_summary/items?${params.toString()}`);
  },

  // Get variables (distinct variable_name values)
  getVariables: async (table = 'sim_metrics_by_location') => {
    return apiCall(`/collections/${table}/queryables/variable_name/values`);
  },

  // Get table properties (now via queryables endpoint)
  getTableProperties: (table = 'sim_metrics_by_location') => {
    return apiCall(`/collections/${table}/queryables`);
  },

  // Get table properties for multiple tables in batch
  getTablePropertiesBatch: async (tables = ['sim_metrics_by_location']) => {
    const results = await Promise.all(
      tables.map(table => apiCall(`/collections/${table}/queryables`))
    );
    // Return as object keyed by table name
    return tables.reduce((acc, table, idx) => {
      acc[table] = results[idx];
      return acc;
    }, {});
  },

  // Get metrics with filtering (OGC API - Features)
  getMetrics: (filters = {}) => {
    const params = new URLSearchParams();
    const table = filters.table || 'sim_metrics_by_location';

    if (filters.configuration) params.append('configuration_name', filters.configuration);
    if (filters.variable) params.append('variable_name', filters.variable);
    if (filters.primary_location_id) params.append('location_id', filters.primary_location_id);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);

    const queryString = params.toString();
    const endpoint = queryString
      ? `/collections/${table}/items?${queryString}`
      : `/collections/${table}/items`;

    return apiCall(endpoint);
  },

  // Get primary timeseries (simple JSON array format)
  getPrimaryTimeseries: (primaryLocationId, filters = {}) => {
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
    params.append('f', 'timeseries'); // Request timeseries format

    return apiCall(`/collections/primary_timeseries/items?${params.toString()}`);
  },

  // Get secondary timeseries (simple JSON array format)
  getSecondaryTimeseries: (primaryLocationId, filters = {}) => {
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
    params.append('f', 'timeseries'); // Request timeseries format

    return apiCall(`/collections/secondary_timeseries/items?${params.toString()}`);
  },

  // Get available collections (OGC API - Common)
  getCollections: () => apiCall('/collections'),

  // Get landing page (OGC API - Common)
  getLandingPage: () => apiCall('/'),

  // Get conformance (OGC API - Common)
  getConformance: () => apiCall('/conformance'),

  // Health check
  healthCheck: () => apiCall('/health'),

  // Auth info
  getMe: () => apiCall('/auth/me'),

  // API key management (admin JWT required)
  listApiKeys: () => apiCall('/auth/api-keys'),
  createApiKey: (name, scopes = []) =>
    apiCall('/auth/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, scopes }),
    }),
  revokeApiKey: (keyId) =>
    apiCall(`/auth/api-keys/${encodeURIComponent(keyId)}`, {
      method: 'DELETE',
    }),

  // Get locations filtered by ID prefix, returns GeoJSON FeatureCollection
  getLocationsByPrefix: (prefix, limit = 5000) => {
    const params = new URLSearchParams();
    params.append('prefix', prefix);
    params.append('limit', limit);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get location id + name (no geometry) filtered by prefix, returns {items: [{id, name}]}
  getLocationIdNames: (prefix, limit = null) => {
    const params = new URLSearchParams();
    if (prefix) params.append('prefix', prefix);
    params.append('include_geometry', 'false');
    if (limit != null) params.append('limit', limit);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get attribute definitions (name, description, type, updated_at, etc.)
  getAttributes: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit);
    params.append('offset', offset);
    return apiCall(`/collections/attributes/items?${params.toString()}`);
  },

  // Get configuration completeness heatmap data
  getCompletenessHeatmap: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    return apiCall(`/collections/configuration_completeness/items?${params.toString()}`);
  },

  // Get location attributes for specified attribute names (EAV rows, one per location+name)
  // Returns {items: [{location_id, attribute_name, value}, ...]}
  getLocationAttributesByNames: (attributeNames = [], limit = null) => {
    const params = new URLSearchParams();
    attributeNames.forEach((name) => params.append('attribute_name', name));
    if (limit != null) params.append('limit', limit);
    return apiCall(`/collections/location_attributes/items?${params.toString()}`);
  },

  // Get a single location by id from the locations table
  // Returns a GeoJSON FeatureCollection with the matching feature
  getLocationById: (id) => {
    const params = new URLSearchParams();
    params.append('id', id);
    params.append('limit', 1);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get configurations_by_location rows for a specific location_id (all rows for that location)
  getConfigurationsByLocationId: (locationId) => {
    const params = new URLSearchParams();
    params.append('location_id', locationId);
    return apiCall(`/collections/configurations_by_location/expanded?${params.toString()}`);
  },

  // Get GeoJSON for all locations matching a configuration + variable via a backend JOIN (no URL-length limit)
  getConfigurationLocationsGeojson: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    return apiCall(`/collections/configurations_by_location/locations-geojson?${params.toString()}`);
  },
};

export default apiService;

// ---------------------------------------------------------------------------
// Gridded / xpublish API
// Separate service backed by VITE_XPUBLISH_API_BASE_URL (the xpublish app).
// ---------------------------------------------------------------------------

const GRIDDED_API_BASE_URL = import.meta.env.VITE_XPUBLISH_API_BASE_URL || 'http://127.0.0.1:8001';
export { GRIDDED_API_BASE_URL };

const griddedApiCall = async (path) => {
  const url = `${GRIDDED_API_BASE_URL}${path}`;
  try {
    const token = await ensureFreshToken();
    const headers = { Accept: 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const response = await fetch(url, { headers });
    if (!response.ok) {
      throw new Error(`Gridded API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  } catch (error) {
    console.error(`Gridded API call failed for ${path}:`, error);
    throw error;
  }
};

export const griddedApiService = {
  // List available dataset keys from the xpublish app
  // GET /api/dataset-keys → { datasets: string[] }
  getGriddedDatasets: () => griddedApiCall('/api/dataset-keys'),

  // List data variables for a dataset
  // GET /api/dataset-variables/{datasetId} → { variables: string[] }
  getGriddedVariables: (datasetId) =>
    griddedApiCall(`/api/dataset-variables/${encodeURIComponent(datasetId)}`),

  // List available timesteps for a dataset (uses the 'time' coordinate)
  // GET /api/datasets/{datasetId}/coords/time → { values: string[] }
  getGriddedTimesteps: (datasetId) =>
    griddedApiCall(`/api/datasets/${encodeURIComponent(datasetId)}/coords/time`),

  // Build the MapLibre raster tile URL template for a given dataset/variable/timestep.
  // Note: {z}/{y}/{x} order (y before x) is required by TilesPlugin.
  // MapLibre substitutes {z}, {x}, {y} independently, so the path order is preserved.
  buildGriddedTileUrl: (datasetId, variable, timestep, colorRamp = 'raster/plasma', min = 0, max = 100) => {
    const params = new URLSearchParams({
      variables: variable,
      style: colorRamp,
      colorscalerange: `${min},${max}`,
      width: '256',
      height: '256',
      f: 'image/png',
      time: timestep,
    });
    return `${GRIDDED_API_BASE_URL}/api/datasets/${encodeURIComponent(datasetId)}/tiles/WebMercatorQuad/{z}/{y}/{x}?${params.toString()}`;
  },

  // Query a single point via the CfEdrPlugin OGC EDR position endpoint.
  // Returns the numeric value at the given lon/lat for the selected variable/timestep,
  // or null if the response cannot be parsed.
  fetchGriddedEdrPoint: async (datasetId, variable, timestep, lon, lat) => {
    const params = new URLSearchParams({
      coords: `POINT(${lon} ${lat})`,
      'parameter-name': variable,
      datetime: timestep,
      f: 'geojson',
    });
    const path = `/api/datasets/${encodeURIComponent(datasetId) + '_raw_data'}/edr/position?${params.toString()}`;
    const data = await griddedApiCall(path);

    // CoverageJSON / GeoJSON response — parse value from the first feature property
    // matching the variable name. Verify against a live response and adjust if needed.
    try {
      const ranges = data?.ranges ?? data?.properties?.ranges ?? {};
      const range = ranges[variable] ?? Object.values(ranges)[0];
      const values = range?.values ?? range?.data;
      return Array.isArray(values) ? values[0] : null;
    } catch {
      return null;
    }
  },
};