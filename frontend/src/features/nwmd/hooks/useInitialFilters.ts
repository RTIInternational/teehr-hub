import { useEffect } from 'react';

import { NWMD_DASHBOARD_DEFAULTS, selectDefault } from '@/config/dashboardDefaults';
import { useConfigurations } from '@/shared/queries/configurations';
import { useDistinctValues } from '@/shared/queries/distinctValues';
import { useVariables } from '@/shared/queries/variables';
import { combineLoadingStates } from '@/shared/utils/loading';

import { ActionTypes, useDashboard } from '../DashboardContext';
import {
  getFilterSelectionsByConfig,
  getConfigurationFilter,
  shouldInitializeFilters,
} from '../utils/filters';

/**
 * Load filters from the data warehouse API and apply defaults.
 * Lead time bins depend on the chosen configuration, so the initial lead time
 * bin query is scoped to the resolved default configuration.
 */
export const useInitialFilters = (table: string) => {
  const { state, dispatch } = useDashboard();

  const configurations = useConfigurations(table);
  const variables = useVariables(table);

  const defaultConfiguration = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredConfiguration,
    configurations.data ?? []
  );
  const configurationFilter = getConfigurationFilter(defaultConfiguration ?? undefined);

  const waterYears = useDistinctValues(table, 'water_year', configurationFilter);
  const quarters = useDistinctValues(table, 'quarter', configurationFilter);
  const thresholds = useDistinctValues(table, 'threshold', configurationFilter);
  const aggMethods = useDistinctValues(table, 'window_agg', configurationFilter);
  const leadTimeBins = useDistinctValues(table, 'forecast_lead_time_bin', configurationFilter);

  const defaultVariable = selectDefault(
    NWMD_DASHBOARD_DEFAULTS.preferredVariable,
    variables.data ?? []
  );

  useEffect(() => {
    if (
      !waterYears.data?.length ||
      !variables.data?.length ||
      !aggMethods.data?.length ||
      !leadTimeBins.data?.length
    ) {
      return;
    }

    if (defaultConfiguration === null || defaultVariable === null) return;

    const nextSelections = getFilterSelectionsByConfig(state.mapFilters, {
      waterYears: waterYears.data,
      quarters: (quarters.data ?? []).filter((quarter): quarter is string => !!quarter),
      thresholds: thresholds.data ?? [],
      aggMethods: aggMethods.data ?? [],
      leadTimeBins: leadTimeBins.data ?? [],
    });

    const nextPayload = {
      configuration: defaultConfiguration,
      variable: defaultVariable,
      ...nextSelections,
    };

    if (!shouldInitializeFilters(state.mapFilters, nextPayload)) {
      return;
    }

    dispatch({
      type: ActionTypes.INITIALIZE_FILTERS,
      payload: nextPayload,
    });
  }, [
    state.mapFilters,
    waterYears.data,
    quarters.data,
    configurations.data,
    variables.data,
    thresholds.data,
    aggMethods.data,
    leadTimeBins.data,
    defaultConfiguration,
    defaultVariable,
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
