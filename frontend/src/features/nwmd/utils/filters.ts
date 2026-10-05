import type { QueryClient } from '@tanstack/react-query';

import { NWMD_DASHBOARD_DEFAULTS, selectDefault } from '@/config/dashboardDefaults';
import { distinctValuesQuery } from '@/shared/queries/distinctValues';
import { getWaterYearForQuarter } from '@/shared/utils/dates';

import type { NwmdMapFilters } from '../types/maps';
import { sortLeadTimeBins } from './leadTimeBins';

type NullableString = string | null;

export type ConfigurationScopedOptions = {
  waterYears: NullableString[];
  quarters: string[];
  thresholds: NullableString[];
  aggMethods: string[];
  leadTimeBins: string[];
};

export const getConfigurationFilter = (configuration?: string) =>
  configuration ? { configuration_name: configuration } : undefined;

const pickLatestValue = (values: NullableString[]) =>
  values.filter((value): value is string => !!value).sort((a, b) => b.localeCompare(a))[0] ?? null;

export const getAvailableQuartersForWaterYear = (
  quarters: string[],
  waterYear: NullableString | undefined
) => {
  if (waterYear === null) {
    return [null];
  }

  return [
    null,
    ...quarters
      .filter((quarter) => !waterYear || getWaterYearForQuarter(quarter) === waterYear)
      .sort((a, b) => a.localeCompare(b)),
  ];
};

export const getFilterSelectionsByConfig = (
  currentFilters: Pick<
    NwmdMapFilters,
    'waterYear' | 'quarter' | 'threshold' | 'aggMethod' | 'leadTimeBin'
  >,
  options: ConfigurationScopedOptions
) => {
  const waterYear =
    currentFilters.waterYear !== undefined && options.waterYears.includes(currentFilters.waterYear)
      ? currentFilters.waterYear
      : pickLatestValue(options.waterYears);

  const availableQuarters = getAvailableQuartersForWaterYear(options.quarters, waterYear);
  const quarter =
    currentFilters.quarter !== undefined && availableQuarters.includes(currentFilters.quarter)
      ? currentFilters.quarter
      : pickLatestValue(availableQuarters);

  const threshold =
    currentFilters.threshold !== undefined && options.thresholds.includes(currentFilters.threshold)
      ? currentFilters.threshold
      : selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredThreshold, options.thresholds);

  const aggMethod =
    currentFilters.aggMethod != null && options.aggMethods.includes(currentFilters.aggMethod)
      ? currentFilters.aggMethod
      : selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredAggMethod, options.aggMethods);

  const orderedLeadTimeBins = sortLeadTimeBins(options.leadTimeBins);
  const leadTimeBin =
    currentFilters.leadTimeBin != null && orderedLeadTimeBins.includes(currentFilters.leadTimeBin)
      ? currentFilters.leadTimeBin
      : selectDefault(NWMD_DASHBOARD_DEFAULTS.preferredLeadTimeBin, orderedLeadTimeBins);

  return {
    waterYear,
    quarter,
    threshold,
    aggMethod,
    leadTimeBin,
  };
};

export const shouldInitializeFilters = (
  currentFilters: Pick<
    NwmdMapFilters,
    | 'configuration'
    | 'variable'
    | 'waterYear'
    | 'quarter'
    | 'threshold'
    | 'aggMethod'
    | 'leadTimeBin'
  >,
  nextFilters: Pick<
    NwmdMapFilters,
    | 'configuration'
    | 'variable'
    | 'waterYear'
    | 'quarter'
    | 'threshold'
    | 'aggMethod'
    | 'leadTimeBin'
  >
) =>
  currentFilters.configuration !== (currentFilters.configuration ?? nextFilters.configuration) ||
  currentFilters.variable !== (currentFilters.variable ?? nextFilters.variable) ||
  currentFilters.waterYear !== nextFilters.waterYear ||
  currentFilters.quarter !== (currentFilters.quarter ?? nextFilters.quarter) ||
  currentFilters.threshold !==
    (currentFilters.threshold !== undefined ? currentFilters.threshold : nextFilters.threshold) ||
  currentFilters.aggMethod !== (currentFilters.aggMethod ?? nextFilters.aggMethod) ||
  currentFilters.leadTimeBin !== (currentFilters.leadTimeBin ?? nextFilters.leadTimeBin);

export const fetchFilterOptionsByConfig = async (
  queryClient: QueryClient,
  table: string,
  configuration: string
): Promise<ConfigurationScopedOptions> => {
  const filters = getConfigurationFilter(configuration);

  const [waterYears, quarters, thresholds, aggMethods, leadTimeBins] = await Promise.all([
    queryClient.fetchQuery(distinctValuesQuery(table, 'water_year', filters)),
    queryClient.fetchQuery(distinctValuesQuery(table, 'quarter', filters)),
    queryClient.fetchQuery(distinctValuesQuery(table, 'threshold', filters)),
    queryClient.fetchQuery(distinctValuesQuery(table, 'window_agg', filters)),
    queryClient.fetchQuery(distinctValuesQuery(table, 'forecast_lead_time_bin', filters)),
  ]);

  return {
    waterYears,
    quarters,
    thresholds,
    aggMethods,
    leadTimeBins,
  };
};
