/**
 * Mapping of duration name tokens (embedded in variable names) to ISO 8601 duration codes.
 * Variable names follow the form <variable>_<duration>_<statistic>
 * (e.g. "streamflow_hourly_inst").
 *
 * To support a new duration, add an entry here — no other code changes are needed.
 */
export const DURATION_NAME_TO_ISO = {
  '15min': 'PT15M',
  'hourly': 'PT1H',
};

/**
 * Inverse of DURATION_NAME_TO_ISO — auto-derived so the two maps never diverge.
 * Maps ISO 8601 duration codes back to their duration name tokens.
 */
export const ISO_TO_DURATION_NAME = Object.fromEntries(
  Object.entries(DURATION_NAME_TO_ISO).map(([name, iso]) => [iso, name])
);

/**
 * Parse duration info from a variable name of the form
 * <variable>_<duration>_<statistic> (e.g. "streamflow_hourly_inst").
 *
 * Returns { duration: isoCode } when the statistic token is "inst" and the
 * duration token is recognised in DURATION_NAME_TO_ISO.
 * Returns { duration: null } for all non-inst statistics (e.g. _mean, _max).
 *
 * Throws if the variable name has fewer than three underscore-separated parts,
 * or if the statistic is "inst" but the duration token is not in the map.
 *
 * @param {string} variableName
 * @returns {{ duration: string|null }}
 */
export function parseVariableInfo(variableName) {
  const parts = variableName.split('_');
  if (parts.length < 3) {
    throw new Error(
      `Variable name "${variableName}" does not match the expected ` +
      '<variable>_<duration>_<statistic> format.'
    );
  }

  const statistic = parts[parts.length - 1];
  if (statistic !== 'inst') {
    return { duration: null };
  }

  const durationToken = parts[parts.length - 2];
  const isoCode = DURATION_NAME_TO_ISO[durationToken];
  if (!isoCode) {
    throw new Error(
      `Unrecognised duration token "${durationToken}" in variable "${variableName}". ` +
      'Add it to DURATION_NAME_TO_ISO in durationUtils.js to support it.'
    );
  }

  return { duration: isoCode };
}

/**
 * Convert a variable name to its primary_timeseries equivalent by replacing
 * the duration token with "none" (e.g. "streamflow_hourly_inst" -> "streamflow_none_inst").
 *
 * Only applies when the statistic token is "inst". Non-inst variables are returned unchanged.
 *
 * @param {string} variableName
 * @returns {string}
 */
export function toPrimaryVariableName(variableName) {
  const parts = variableName.split('_');
  if (parts.length < 3) return variableName;
  if (parts[parts.length - 1] !== 'inst') return variableName;
  const result = [...parts];
  result[result.length - 2] = 'none';
  return result.join('_');
}

/**
 * Expand primary_timeseries variable names (e.g. 'streamflow_none_inst') into
 * all duration variants by replacing the 'none' token with every key in
 * DURATION_NAME_TO_ISO (e.g. ['streamflow_15min_inst', 'streamflow_hourly_inst']).
 *
 * Variables that do not match the <var>_none_inst pattern are returned unchanged.
 *
 * @param {string[]} primaryVariableNames
 * @returns {string[]}
 */
export function expandPrimaryVariables(primaryVariableNames) {
  const durationKeys = Object.keys(DURATION_NAME_TO_ISO);
  return primaryVariableNames.flatMap(varName => {
    const parts = varName.split('_');
    if (
      parts.length < 3 ||
      parts[parts.length - 2] !== 'none' ||
      parts[parts.length - 1] !== 'inst'
    ) {
      return [varName];
    }
    return durationKeys.map(token => {
      const result = [...parts];
      result[result.length - 2] = token;
      return result.join('_');
    });
  });
}

/**
 * Group an array of variable names by their ISO 8601 duration code.
 * Variables whose statistic is not "inst" are grouped under the null key.
 *
 * @param {string[]} variables
 * @returns {Map<string|null, string[]>}
 */
export function groupVariablesByDuration(variables) {
  const groups = new Map();
  for (const variable of variables) {
    const { duration } = parseVariableInfo(variable);
    if (!groups.has(duration)) {
      groups.set(duration, []);
    }
    groups.get(duration).push(variable);
  }
  return groups;
}
