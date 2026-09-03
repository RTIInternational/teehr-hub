import { useEffect } from 'react';

import { NWMD_DASHBOARD_DEFAULTS, selectDefault } from '@/config/dashboardDefaults';
import { ActionTypes, useDashboard } from '@/context/NwmdDashboardContext';
import { useConfigurations } from '@/shared/queries/configurations';
import { useDistinctValues } from '@/shared/queries/distinctValues';
import { useVariables } from '@/shared/queries/variables';

/**
 * Load filters from data warehouse API and apply defaults
 * @param table Data warehouse table to reference in queries
 * @returns UseQueryResult objects for distinct values
 */
export const useInitialFilters = (table: string) => {
  const { dispatch } = useDashboard();

  const quarters = useDistinctValues(table, 'quarter');
  const configurations = useConfigurations(table);
  const variables = useVariables(table);
  const thresholds = useDistinctValues(table, 'threshold');
  const aggMethods = useDistinctValues(table, 'window_agg');
  const leadTimeBins = useDistinctValues(table, 'forecast_lead_time_bin');

  const defaultQuarter = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredQuarter,
    quarters.data ?? []
  );

  const defaultConfiguration = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredConfiguration,
    configurations.data ?? []
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
      defaultQuarter == null ||
      defaultConfiguration == null ||
      defaultVariable == null ||
      defaultAggMethod == null ||
      defaultLeadTimeBin == null
    ) {
      return;
    }

    dispatch({
      type: ActionTypes.INITIALIZE_FILTERS,
      payload: {
        quarter: defaultQuarter,
        configuration: defaultConfiguration,
        variable: defaultVariable,
        threshold: defaultThreshold ?? null,
        aggMethod: defaultAggMethod,
        leadTimeBin: defaultLeadTimeBin,
      },
    });
  }, [
    defaultQuarter,
    defaultConfiguration,
    defaultVariable,
    defaultThreshold,
    defaultAggMethod,
    defaultLeadTimeBin,
    dispatch,
  ]);

  return {
    quarters,
    configurations,
    variables,
    thresholds,
    aggMethods,
    leadTimeBins,
  };
};
