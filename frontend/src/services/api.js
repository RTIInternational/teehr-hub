// API configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

// Helper function for API calls
const apiCall = async (endpoint, options = {}) => {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
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

// API service object
export const apiService = {
  // Get all locations
  getLocations: () => apiCall('/api/locations'),
  
  // Get configurations
  getConfigurations: () => apiCall('/api/configurations'),
  
  // Get variables
  getVariables: () => apiCall('/api/variables'),
  
  // Get metric names
  getMetricNames: () => apiCall('/api/metric-names'),
  
  // Get metrics with filtering
  getMetrics: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration) params.append('configuration', filters.configuration);
    if (filters.variable) params.append('variable', filters.variable);
    
    const queryString = params.toString();
    const endpoint = queryString ? `/api/metrics?${queryString}` : '/api/metrics';
    
    return apiCall(endpoint);
  },
  
  // Get primary timeseries
  getPrimaryTimeseries: (locationId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.variable) params.append('variable', filters.variable);
    
    const queryString = params.toString();
    const endpoint = queryString 
      ? `/api/timeseries/primary/${locationId}?${queryString}`
      : `/api/timeseries/primary/${locationId}`;
    
    return apiCall(endpoint);
  },
  
  // Get secondary timeseries
  getSecondaryTimeseries: (locationId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.start_date) params.append('start_date', filters.start_date);
    if (filters.end_date) params.append('end_date', filters.end_date);
    if (filters.configuration) params.append('configuration', filters.configuration);
    if (filters.variable) params.append('variable', filters.variable);
    
    const queryString = params.toString();
    const endpoint = queryString 
      ? `/api/timeseries/secondary/${locationId}?${queryString}`
      : `/api/timeseries/secondary/${locationId}`;
    
    return apiCall(endpoint);
  },
  
  // Get timeseries data
  getTimeseries: (locationId, filters = {}) => {
    const params = new URLSearchParams();
    if (filters.configuration) params.append('configuration', filters.configuration);
    if (filters.variable) params.append('variable', filters.variable);
    if (filters.reference_time) params.append('reference_time', filters.reference_time);
    
    const queryString = params.toString();
    const endpoint = queryString 
      ? `/api/timeseries/${locationId}?${queryString}`
      : `/api/timeseries/${locationId}`;
    
    return apiCall(endpoint);
  },

  // Health check
  healthCheck: () => apiCall('/health'),
};

export default apiService;