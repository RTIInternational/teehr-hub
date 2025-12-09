/**
 * Utility functions for formatting variable names, units, and labels
 */

/**
 * Format variable names from snake_case to Title Case with optional lookup overrides
 * @param {string} variableName - The variable name to format
 * @returns {string} Formatted variable name
 */
export const formatVariableName = (variableName) => {
  if (!variableName) return 'Value';
  
  // Lookup table for variable name overrides
  const variableLookup = {
    'streamflow_hourly_inst': 'Streamflow (Hourly Instantaneous)',
    'streamflow_daily_mean': 'Streamflow (Daily Mean)',
    'precipitation': 'Precipitation',
    'temperature': 'Temperature',
    'water_temperature': 'Water Temperature'
  };
  
  // Return override if exists, otherwise convert snake_case to Title Case
  return variableLookup[variableName] || 
    variableName
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
};

/**
 * Format unit names with lookup overrides for common units
 * @param {string} unitName - The unit name to format
 * @returns {string} Formatted unit name
 */
export const formatUnitName = (unitName) => {
  if (!unitName) return '';
  
  // Lookup table for unit overrides
  const unitLookup = {
    'm3/s': 'm³/s',
    'm^3/s': 'm³/s',
    'cubic_meters_per_second': 'm³/s',
    'cms': 'm³/s',
    'cfs': 'ft³/s',
    'cubic_feet_per_second': 'ft³/s',
    'deg_c': '°C',
    'celsius': '°C',
    'deg_f': '°F',
    'fahrenheit': '°F',
    'millimeters': 'mm',
    'inches': 'in',
    'meters': 'm',
    'feet': 'ft'
  };
  
  // Return override if exists, otherwise return raw string
  return unitLookup[unitName.toLowerCase()] || unitName;
};

/**
 * Create a formatted Y-axis title with variable name and units
 * @param {Array} primaryData - Primary timeseries data
 * @param {Array} secondaryData - Secondary timeseries data  
 * @param {Object} filters - Current filter settings
 * @returns {string} Formatted Y-axis title
 */
export const getYAxisTitle = (primaryData, secondaryData, filters) => {
  // Try to get unit from the data first
  let unit = null;
  let variable = null;
  
  if (primaryData?.length > 0 && primaryData[0]?.unit_name) {
    unit = primaryData[0].unit_name;
    variable = primaryData[0].variable_name || filters.variable;
  } else if (secondaryData?.length > 0 && secondaryData[0]?.unit_name) {
    unit = secondaryData[0].unit_name;
    variable = secondaryData[0].variable_name || filters.variable;
  }
  
  // Format the variable and unit names
  const formattedVariable = formatVariableName(variable || filters.variable);
  const formattedUnit = formatUnitName(unit);
  
  // Return formatted title
  if (formattedUnit) {
    return `${formattedVariable} (${formattedUnit})`;
  }
  
  return formattedVariable;
};