/**
 * Compute CDF points for given locations by metric
 * @param {Object} locations - OGC locations returned from metrics endpoint
 * @param {string} metric - property/column name to use for CDF computation
 * @returns {array} an array of [x, y] points
 */
export const computeCdfData = (locations, metric) => {
  if (!Array.isArray(locations) || !metric) return [];

  const values = locations
    .map((location) => location?.properties?.[metric])
    .filter((value) => Number.isFinite(value));

  if (values.length === 0) return [];

  const sortedValues = values.toSorted((a, b) => a - b);
  const n = sortedValues.length;
  const cdfPoints = sortedValues.map((value, i) => [value, (i + 1.0) / n]);

  return cdfPoints;
};
