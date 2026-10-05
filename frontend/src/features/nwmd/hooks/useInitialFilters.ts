import { useEffect } from 'react';

import { NWMD_DASHBOARD_DEFAULTS, selectDefault } from '@/config/dashboardDefaults';
import { useConfigurations } from '@/shared/queries/configurations';
import { useDistinctValues } from '@/shared/queries/distinctValues';
import { useVariables } from '@/shared/queries/variables';
import { combineLoadingStates } from '@/shared/utils/loading';

import { ActionTypes, useDashboard } from '../DashboardContext';

/**
 * Load filters from the data warehouse API and apply defaults.
 * Lead time bins depend on the chosen configuration, so the initial lead time
 * bin query is scoped to the resolved default configuration.
 */
export const useInitialFilters = (table: string) => {
  const { dispatch } = useDashboard();

  const waterYears = useDistinctValues(table, 'water_year');
  const quarters = useDistinctValues(table, 'quarter');
  const configurations = useConfigurations(table);
  const variables = useVariables(table);
  const thresholds = useDistinctValues(table, 'threshold');
  const aggMethods = useDistinctValues(table, 'window_agg');

  const defaultConfiguration = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredConfiguration,
    configurations.data ?? []
  );

  const leadTimeBins = useDistinctValues(
    table,
    'forecast_lead_time_bin',
    defaultConfiguration ? { configuration_name: defaultConfiguration } : undefined
  );

  const defaultVariable = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredVariable,
    variables.data ?? []
  );

  const defaultThreshold = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredThreshold,
    thresholds.data ?? []
  );

  const defaultAggMethod = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredAggMethod,
    aggMethods.data ?? []
  );

  const defaultLeadTimeBin = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredLeadTimeBin,
    leadTimeBins.data ?? []
  );

  useEffect(() => {
    if (
      !waterYears.data?.length ||
      !configurations.data?.length ||
      !variables.data?.length ||
      !aggMethods.data?.length ||
      !leadTimeBins.data?.length
    ) {
      return;
    }

    if (defaultConfiguration === null || defaultVariable === null) return;

    const defaultWaterYear = waterYears.data
      .filter((waterYear) => !!waterYear)
      .sort((a, b) => (a < b ? 1 : -1))[0];

    const defaultQuarter = (quarters.data ?? [])
      .filter((quarter): quarter is string => !!quarter)
      .sort((a, b) => (a < b ? 1 : -1))[0];

    dispatch({
      type: ActionTypes.INITIALIZE_FILTERS,
      payload: {
        waterYear: defaultWaterYear,
        quarter: defaultQuarter ?? null,
        configuration: defaultConfiguration,
        variable: defaultVariable,
        threshold: defaultThreshold ?? null,
        aggMethod: defaultAggMethod,
        leadTimeBin: defaultLeadTimeBin,
      },
    });
  }, [
    waterYears.data,
    quarters.data,
    configurations.data,
    variables.data,
    aggMethods.data,
    leadTimeBins.data,
    defaultConfiguration,
    defaultVariable,
    defaultAggMethod,
    defaultLeadTimeBin,
    defaultThreshold,
    dispatch,
  ]);

  return {
    quarters,
    configurations,
    variables,
    thresholds,
    aggMethods,
    leadTimeBins,
    isLoading: combineLoadingStates(
      waterYears,
      quarters,
      configurations,
      variables,
      thresholds,
      aggMethods,
      leadTimeBins
    ),
  };
};
