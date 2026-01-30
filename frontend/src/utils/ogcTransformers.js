/**
 * Utilities to transform OGC API responses to dashboard-friendly formats
 */

/**
 * Extract configuration/variable options from OGC Queryables schema
 * The queryables endpoint returns a JSON Schema with x-teehr-role extensions
 * 
 * @param {Object} queryables - OGC Queryables response
 * @returns {Object} - { groupByFields: [...], metricFields: [...] }
 */
export const parseQueryables = (queryables) => {
  if (!queryables?.properties) {
    return { groupByFields: [], metricFields: [] };
  }

  const groupByFields = [];
  const metricFields = [];

  for (const [fieldName, fieldSchema] of Object.entries(queryables.properties)) {
    const role = fieldSchema['x-teehr-role'];
    
    if (role === 'group_by') {
      groupByFields.push({
        name: fieldName,
        title: fieldSchema.title || fieldName,
        type: fieldSchema.type || 'string',
      });
    } else if (role === 'metric') {
      metricFields.push({
        name: fieldName,
        title: fieldSchema.title || fieldName,
        type: fieldSchema.type || 'number',
      });
    }
  }

  return { groupByFields, metricFields };
};

/**
 * Extract TEEHR extension data from queryables
 * @param {Object} queryables - OGC Queryables response
 * @returns {Object} - { group_by: [...], metrics: [...], description: string }
 */
export const extractTableProperties = (queryables) => {
  return {
    // Use underscores to match component expectations
    group_by: queryables['x-teehr-group-by'] || [],
    groupBy: queryables['x-teehr-group-by'] || [],  // Alias for backwards compatibility
    metrics: queryables['x-teehr-metrics'] || [],
    description: queryables.description || '',
    title: queryables.title || '',
  };
};

/**
 * Transform CoverageJSON timeseries to chart-friendly format
 * 
 * CoverageJSON structure:
 * {
 *   type: "Coverage",
 *   domain: { axes: { t: { values: ["2020-01-01T00:00:00Z", ...] } } },
 *   ranges: { parameter_name: { values: [1.2, 3.4, ...] } }
 * }
 * 
 * @param {Object} coverageJson - CoverageJSON response
 * @returns {Array} - Array of { time, value, parameter } objects
 */
export const parseCoverageJson = (coverageJson) => {
  if (!coverageJson || coverageJson.type !== 'Coverage') {
    console.warn('Invalid CoverageJSON response:', coverageJson);
    return [];
  }

  const times = coverageJson.domain?.axes?.t?.values || [];
  const ranges = coverageJson.ranges || {};
  const result = [];

  // Process each parameter (range) in the coverage
  for (const [paramName, paramData] of Object.entries(ranges)) {
    const values = paramData.values || [];
    const unit = paramData.unit?.symbol || paramData.unit?.label?.en || '';
    
    times.forEach((time, idx) => {
      if (values[idx] !== null && values[idx] !== undefined) {
        result.push({
          time: new Date(time),
          timeString: time,
          value: values[idx],
          parameter: paramName,
          unit: unit,
        });
      }
    });
  }

  return result;
};

/**
 * Transform CoverageJSON to timeseries arrays grouped by parameter
 * Better for charting libraries that want separate series
 * 
 * @param {Object} coverageJson - CoverageJSON response
 * @returns {Object} - { parameterName: [{ time, value }, ...], ... }
 */
export const parseCoverageJsonToSeries = (coverageJson) => {
  if (!coverageJson || coverageJson.type !== 'Coverage') {
    return {};
  }

  const times = coverageJson.domain?.axes?.t?.values || [];
  const ranges = coverageJson.ranges || {};
  const series = {};

  for (const [paramName, paramData] of Object.entries(ranges)) {
    const values = paramData.values || [];
    
    series[paramName] = times.map((time, idx) => ({
      time: new Date(time),
      timeString: time,
      value: values[idx],
    })).filter(d => d.value !== null && d.value !== undefined);
  }

  return series;
};

/**
 * Extract location coordinates from CoverageJSON domain
 * @param {Object} coverageJson - CoverageJSON response
 * @returns {Object|null} - { lon, lat } or null
 */
export const extractCoverageLocation = (coverageJson) => {
  if (!coverageJson?.domain?.axes) {
    return null;
  }

  const { x, y } = coverageJson.domain.axes;
  
  if (x?.values?.[0] !== undefined && y?.values?.[0] !== undefined) {
    return {
      lon: x.values[0],
      lat: y.values[0],
    };
  }

  return null;
};

/**
 * Get list of parameters from CoverageJSON
 * @param {Object} coverageJson - CoverageJSON response
 * @returns {Array} - Array of parameter info objects
 */
export const getCoverageParameters = (coverageJson) => {
  if (!coverageJson?.parameters) {
    return [];
  }

  return Object.entries(coverageJson.parameters).map(([id, param]) => ({
    id,
    label: param.observedProperty?.label?.en || id,
    description: param.description?.en || '',
    unit: param.unit?.symbol || param.unit?.label?.en || '',
  }));
};

/**
 * Transform GeoJSON features to flat array of properties
 * For backwards compatibility with code expecting simple arrays
 * 
 * @param {Object} geojson - GeoJSON FeatureCollection
 * @returns {Array} - Array of feature properties with geometry info
 */
export const flattenGeoJsonFeatures = (geojson) => {
  if (!geojson?.features) {
    return [];
  }

  return geojson.features.map(feature => ({
    ...feature.properties,
    geometry: feature.geometry,
    id: feature.id || feature.properties?.id,
  }));
};

/**
 * Transform API response to the format expected by PlotlyChart
 * 
 * API now returns simple JSON array:
 * [{ 
 *   series_type,
 *   primary_location_id,
 *   reference_time,
 *   configuration_name,
 *   variable_name,
 *   unit_name,
 *   member,
 *   timeseries: [{ value_time, value }]
 * }]
 * 
 * PlotlyChart expects the same format, so this is now a pass-through
 * with backwards compatibility for old CoverageJSON format.
 * 
 * @param {Array|Object} data - API response (array or old CoverageJSON)
 * @returns {Array} - Array in PlotlyChart-expected format
 */
export const coverageJsonToPlotlyFormat = (data) => {
  // Handle new simple JSON array format (just return as-is)
  if (Array.isArray(data)) {
    return data;
  }
  
  // Backwards compatibility: Handle old CoverageJSON format if needed
  if (data && data.type === 'Coverage') {
    const times = data.domain?.axes?.t?.values || [];
    const ranges = data.ranges || {};
    const parameters = data.parameters || {};
    const result = [];

    for (const [paramId, rangeData] of Object.entries(ranges)) {
      const values = rangeData.values || [];
      const paramInfo = parameters[paramId] || {};
      
      const timeseries = times.map((time, idx) => ({
        value_time: time,
        value: values[idx],
      })).filter(d => d.value !== null && d.value !== undefined);

      if (timeseries.length > 0) {
        let configName = paramInfo.configurationName;
        let variableName = paramInfo.variableName || paramInfo.observedProperty?.label?.en || paramId;
        
        if (!configName) {
          const description = paramInfo.description?.en || paramId;
          const parts = description.split(' - ');
          configName = parts.length > 1 ? parts.slice(1).join(' - ') : description;
        }
        
        result.push({
          timeseries,
          configuration_name: configName,
          variable_name: variableName,
          unit_name: paramInfo.unit?.symbol || paramInfo.unit?.label?.en || '',
          reference_time: paramInfo.referenceTime || null,
          series_type: data['x-teehr-series-type'] || 'primary',
        });
      }
    }
    return result;
  }
  
  // Invalid format
  console.warn('Invalid timeseries response format:', data);
  return [];
};

export default {
  parseQueryables,
  extractTableProperties,
  parseCoverageJson,
  parseCoverageJsonToSeries,
  extractCoverageLocation,
  getCoverageParameters,
  flattenGeoJsonFeatures,
  coverageJsonToPlotlyFormat,
};
