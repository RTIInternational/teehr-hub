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
    
    if (filters.configuration) params.append('configuration', filters.configuration);
    if (filters.variable) params.append('parameter', filters.variable);
    if (filters.primary_location_id) params.append('location_id', filters.primary_location_id);
    if (filters.limit) params.append('limit', filters.limit);
    if (filters.offset) params.append('offset', filters.offset);
    
    const queryString = params.toString();
    const endpoint = queryString 
      ? `/collections/${table}/items?${queryString}` 
      : `/collections/${table}/items`;
    
    return apiCall(endpoint);
  },
  
  // Get primary timeseries (OGC API - Coverages)
  getPrimaryTimeseries: (primaryLocationId, filters = {}) => {
    const params = new URLSearchParams();
    params.append('location', primaryLocationId);
    
    // Use ISO 8601 datetime interval
    const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
    if (datetime) params.append('datetime', datetime);
    
    if (filters.variable) params.append('parameter', filters.variable);
    if (filters.configuration) params.append('configuration', filters.configuration);
    
    return apiCall(`/collections/primary_timeseries/coverage?${params.toString()}`);
  },
  
  // Get secondary timeseries (OGC API - Coverages)
  getSecondaryTimeseries: (primaryLocationId, filters = {}) => {
    const params = new URLSearchParams();
    params.append('location', primaryLocationId);
    
    // Use ISO 8601 datetime interval for value_time
    const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
    if (datetime) params.append('datetime', datetime);
    
    // Use ISO 8601 datetime interval for reference_time
    const refDatetime = formatDatetimeInterval(
      filters.reference_start_date, 
      filters.reference_end_date
    );
    if (refDatetime) params.append('reference_time', refDatetime);
    
    if (filters.configuration) params.append('configuration', filters.configuration);
    if (filters.variable) params.append('parameter', filters.variable);
    
    return apiCall(`/collections/secondary_timeseries/coverage?${params.toString()}`);
  },

  // Get available collections (OGC API - Common)
  getCollections: () => apiCall('/collections'),

  // Get landing page (OGC API - Common)
  getLandingPage: () => apiCall('/'),

  // Get conformance (OGC API - Common)
  getConformance: () => apiCall('/conformance'),

  // Health check
  healthCheck: () => apiCall('/health'),
};

export default apiService;