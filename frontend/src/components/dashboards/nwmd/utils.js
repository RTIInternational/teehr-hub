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

const parseFiniteNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const evaluateAltHypothesis = (lower, upper, operator) => {
  switch (operator) {
    case "=0":
      return lower <= 0 && upper >= 0;
    case "!=0":
      return upper < 0 || lower > 0;
    case ">0":
      return lower > 0;
    case "<0":
      return upper < 0;
    case ">1":
      return lower > 1;
    case "<1":
      return upper < 1;
    default:
      return true;
  }
};

export const applyAltHypothesisFilter = (
  locations,
  metricName,
  altHypothesis95,
) => {
  if (!altHypothesis95 || !metricName) return locations;

  const features = Array.isArray(locations?.features) ? locations.features : [];
  if (!features.length) return locations;

  const lowerKey = `${metricName}_boot_0_025`;
  const upperKey = `${metricName}_boot_0_975`;
  const hasBootstrapBounds = features.some((feature) => {
    const properties = feature?.properties || {};
    return lowerKey in properties && upperKey in properties;
  });

  if (!hasBootstrapBounds) {
    console.warn(
      `Skipping alt-hypothesis filter: bootstrap CI fields not found for metric '${metricName}'.`,
    );
    return locations;
  }

  const filteredFeatures = features.filter((feature) => {
    const properties = feature?.properties || {};
    const lower = parseFiniteNumber(properties[lowerKey]);
    const upper = parseFiniteNumber(properties[upperKey]);

    if (lower === null || upper === null) return false;

    return evaluateAltHypothesis(lower, upper, altHypothesis95);
  });

  return {
    ...locations,
    features: filteredFeatures,
  };
};

export const NWMD_METRICS = new Set([
  "relative_mean",
  "relative_median",
  "relative_minimum",
  "relative_maximum",
  "relative_standard_deviation",
  "relative_bias",
  "nash_sutcliffe_efficiency",
  "kling_gupta_efficiency",
  "pearson_correlation",
]);
