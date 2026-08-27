/**
 * Normalize a raw configuration name to a short display label.
 * Falls back to the raw value for unrecognized strings.
 */
export const formatConfigurationName = (raw: string): string => {
  const lower = raw.toLowerCase();
  if (lower.includes('benchmark')) return 'Benchmark';
  if (lower.includes('hefs')) return 'HEFS';
  return raw;
};
