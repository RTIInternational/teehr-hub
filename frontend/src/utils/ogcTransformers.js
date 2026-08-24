/**
 * OGC API Transformers
 * 
 * Utilities for transforming OGC API responses into application-friendly formats.
 * Specifically handles queryables responses with x-teehr-role extensions.
 */

/**
 * Extract table properties from an OGC queryables response.
 * 
 * The queryables endpoint returns a JSON Schema with:
 * - Top-level x-teehr-group-by and x-teehr-metrics arrays (preferred)
 * - Per-property x-teehr-role extensions as fallback
 * 
 * @param {Object} queryables - OGC queryables response (JSON Schema)
 * @returns {Object} Extracted properties categorized by role:
 *   - metrics: Array of metric property names
 *   - group_by: Array of group_by property names
 *   - description: Table description from schema
 *   - allProperties: Array of all property names
 */
export const extractTableProperties = (queryables) => {
  if (!queryables || typeof queryables !== 'object') {
    return {
      metrics: [],
      group_by: [],
      description: '',
      allProperties: []
    };
  }

  const properties = queryables.properties || {};
  const allProperties = Object.keys(properties);

  // Prefer top-level arrays if available
  if (queryables['x-teehr-metrics'] && queryables['x-teehr-group-by']) {
    return {
      metrics: queryables['x-teehr-metrics'],
      group_by: queryables['x-teehr-group-by'],
      description: queryables.description || queryables.title || '',
      allProperties
    };
  }

  // Fallback: iterate properties and check x-teehr-role
  const metrics = [];
  const groupBy = [];

  for (const [propName, propSchema] of Object.entries(properties)) {
    const role = propSchema?.['x-teehr-role'];
    
    if (role === 'metric') {
      metrics.push(propName);
    } else if (role === 'group_by') {
      groupBy.push(propName);
    }
  }

  return {
    metrics,
    group_by: groupBy,
    description: queryables.description || queryables.title || '',
    allProperties
  };
};

/**
 * Transform OGC Features response to a simplified array of features with properties.
 * 
 * @param {Object} featureCollection - GeoJSON FeatureCollection
 * @returns {Array} Array of feature properties
 */
export const extractFeatureProperties = (featureCollection) => {
  if (!featureCollection?.features) {
    return [];
  }
  
  return featureCollection.features.map(feature => feature.properties || {});
};

/**
 * Build OGC-compliant CQL filter string from filter object.
 * 
 * @param {Object} filters - Filter key-value pairs
 * @returns {string} CQL filter string
 */
export const buildCqlFilter = (filters) => {
  const conditions = [];
  
  for (const [key, value] of Object.entries(filters)) {
    if (value !== null && value !== undefined && value !== '') {
      if (typeof value === 'string') {
        conditions.push(`${key}='${value}'`);
      } else if (typeof value === 'number') {
        conditions.push(`${key}=${value}`);
      } else if (Array.isArray(value) && value.length > 0) {
        const values = value.map(v => typeof v === 'string' ? `'${v}'` : v).join(',');
        conditions.push(`${key} IN (${values})`);
      }
    }
  }
  
  return conditions.join(' AND ');
};
