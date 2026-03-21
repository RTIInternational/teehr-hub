/**
 * Dashboard default configuration settings
 * 
 * These settings control the default selections when the dashboard loads.
 * Update these values as new configurations become available.
 */

export const RETROSPECTIVE_DASHBOARD_DEFAULTS = {
  // Preferred default configuration - will be selected if available in the payload
  // Falls back to first available configuration if not found
  preferredConfiguration: 'nwm30_retrospective',
  
  // Preferred default variable - will be selected if available
  // Falls back to first available variable if not found
  preferredVariable: 'streamflow_hourly_inst',
  
  // Default metric for map coloring
  defaultMetricName: 'relative_bias',
  
  // Default date range for retrospective analysis
  defaultStartDate: '2020-01-01T00:00',
  defaultEndDate: '2020-12-31T23:59'
};

export const FORECAST_DASHBOARD_DEFAULTS = {
  // Preferred default configuration for forecasts
  preferredConfiguration: 'nwm30_medium_range',
  
  // Preferred default variable
  preferredVariable: 'streamflow_hourly_inst',
  
  // Default metric for map coloring
  defaultMetricName: 'relative_bias'
};

/**
 * Helper function to select the best default from available options
 * @param {string|null} preferred - The preferred default value
 * @param {Array} available - Array of available options
 * @returns {string|null} The selected default
 */
export const selectDefault = (preferred, available) => {
  if (!Array.isArray(available) || available.length === 0) {
    return null;
  }
  
  // If preferred value exists in available options, use it
  if (preferred && available.includes(preferred)) {
    return preferred;
  }
  
  // Otherwise fall back to first available option
  return available[0];
};
