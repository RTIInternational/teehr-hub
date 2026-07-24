/**
 * Mapping of duration name tokens (embedded in variable names) to ISO 8601 duration codes.
 * Variable names follow the form <variable>_<duration>_<statistic>
 * (e.g. "streamflow_hourly_inst").
 *
 * To support a new duration, add an entry here — no other code changes are needed.
 */
export const DURATION_NAME_TO_ISO = {
  'Hourly': 'PT1H',
  '15 min': 'PT15M',
};

/**
 * Inverse of DURATION_NAME_TO_ISO — auto-derived so the two maps never diverge.
 * Maps ISO 8601 duration codes back to their duration name tokens.
 */
export const ISO_TO_DURATION_NAME = Object.fromEntries(
  Object.entries(DURATION_NAME_TO_ISO).map(([name, iso]) => [iso, name])
);

/**
 * Convert a raw primary_timeseries variable name to a display name.
 * Replaces the '_none_inst' suffix with '_inst'.
 * All other variable names are returned unchanged.
 *
 * @param {string} rawName
 * @returns {string}
 */
export function toDisplayVariableName(rawName) {
  if (rawName && rawName.endsWith('_none_inst')) {
    return rawName.slice(0, -'_none_inst'.length) + '_inst';
  }
  return rawName;
}

/**
 * Inverse of toDisplayVariableName.
 * Converts '_inst' suffix back to '_none_inst'.
 *
 * @param {string} displayName
 * @returns {string}
 */
export function fromDisplayVariableName(displayName) {
  if (displayName && displayName.endsWith('_inst')) {
    return displayName.slice(0, -'_inst'.length) + '_none_inst';
  }
  return displayName;
}

/**
 * Returns true when the raw variable name ends with '_none_inst',
 * indicating it supports timestep duration filtering.
 *
 * @param {string} rawName
 * @returns {boolean}
 */
export function isTimestepVariable(rawName) {
  return rawName ? rawName.endsWith('_none_inst') : false;
}
