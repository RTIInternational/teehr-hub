import type { LeadTimeMetricsRow } from '../hooks/useLeadTimeMetrics';

const METRIC_KEYS: (keyof LeadTimeMetricsRow)[] = [
  'mean_absolute_error',
  'root_mean_square_error',
  'relative_bias',
  'pearson_correlation',
  'probability_of_detection',
  'false_alarm_ratio',
  'critical_success_index',
  'frequency_bias_index',
  'mean_crps_ensemble',
  'mean_crps_ensemble_skill_score',
  'mean_brier_score',
  'mean_brier_score_skill_score',
];

const SECONDS_PER_DAY = 86400;

/**
 * Aggregates hourly lead time metric rows to daily means.
 *
 * Rows are grouped by configuration, location, variable, season, threshold,
 * and the integer day number derived from `forecast_lead_time` (seconds).
 * All numeric metric columns are averaged within each group. The representative
 * `forecast_lead_time` for each group is the mean of the constituent lead times.
 */
export const aggregateLeadTimeMetricsByDay = (
  rows: LeadTimeMetricsRow[],
): LeadTimeMetricsRow[] => {
  const groups = new Map<string, LeadTimeMetricsRow[]>();

  for (const row of rows) {
    const dayIndex = Math.floor((row.forecast_lead_time as number) / SECONDS_PER_DAY);
    const groupKey = [
      row.primary_location_id,
      row.configuration_name,
      row.variable_name ?? '',
      row.season ?? '',
      row.threshold ?? '',
      dayIndex,
    ].join('\x00');

    if (!groups.has(groupKey)) groups.set(groupKey, []);
    groups.get(groupKey)!.push(row);
  }

  const result: LeadTimeMetricsRow[] = [];

  for (const groupRows of groups.values()) {
    const aggregated: LeadTimeMetricsRow = { ...groupRows[0] };

    // Mean lead time for the day bucket
    aggregated.forecast_lead_time =
      groupRows.reduce((sum, r) => sum + (r.forecast_lead_time as number), 0) / groupRows.length;

    // Null-aware mean for every metric column
    for (const key of METRIC_KEYS) {
      const values = groupRows
        .map((r) => r[key])
        .filter((v): v is number => v != null && Number.isFinite(Number(v)))
        .map(Number);
      (aggregated as Record<string, unknown>)[key as string] =
        values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : null;
    }

    result.push(aggregated);
  }

  result.sort(
    (a, b) => (a.forecast_lead_time as number) - (b.forecast_lead_time as number),
  );

  return result;
};
