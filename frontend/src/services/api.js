// API configuration - OGC-compliant endpoints
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Helper function for API calls
const apiCall = async (endpoint, options = {}) => {
  try {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
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

  // Get locations filtered by ID prefix, returns GeoJSON FeatureCollection
  getLocationsByPrefix: (prefix, limit = 5000) => {
    const params = new URLSearchParams();
    params.append('prefix', prefix);
    params.append('limit', limit);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get distinct spatial aggregate geometries for the completeness overlay map layer
  getCompletenessGeometries: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    return apiCall(`/collections/configuration_completeness/geometries?${params.toString()}`);
  },

  // Get attribute definitions (name, description, type, updated_at, etc.)
  getAttributes: (limit = 1000, offset = 0) => {
    const params = new URLSearchParams();
    params.append('limit', limit);
    params.append('offset', offset);
    return apiCall(`/collections/attributes/items?${params.toString()}`);
  },

  // Get HUC8 weekly aggregation (completeness) data
  getAggregationHuc8Weekly: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    return apiCall(`/collections/configuration_completeness/items?${params.toString()}`);
  },

  // Get configurations_by_location as GeoJSON FeatureCollection (includes geometry)
  getConfigurationsByLocationGeojson: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.variable_name) params.append('variable_name', filters.variable_name);
    if (filters.primary_location_id) params.append('primary_location_id', filters.primary_location_id);
    return apiCall(`/collections/configurations_by_location/geojson?${params.toString()}`);
  },

  // Get configurations_by_location as tabular items (no binary geometry)
  getConfigurationsByLocationItems: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    if (Array.isArray(filters.extra_fields)) {
      filters.extra_fields.forEach((f) => params.append('extra_fields', f));
    }
    return apiCall(`/collections/configurations_by_location/items?${params.toString()}`);
  },

  // Get a single location by id from the locations table
  // Returns a GeoJSON FeatureCollection with the matching feature
  getLocationById: (id) => {
    const params = new URLSearchParams();
    params.append('id', id);
    params.append('limit', 1);
    return apiCall(`/collections/locations/items?${params.toString()}`);
  },

  // Get configurations_by_location row for a specific primary_location_id
  getConfigurationsByLocationForId: (primaryLocationId) => {
    const params = new URLSearchParams();
    params.append('primary_location_id', primaryLocationId);
    params.append('limit', 1);
    return apiCall(`/collections/configurations_by_location/items?${params.toString()}`);
  },
};

export default apiService;