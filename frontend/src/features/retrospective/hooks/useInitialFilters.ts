import { useEffect } from 'react';
import { RETROSPECTIVE_DASHBOARD_DEFAULTS, selectDefault } from '@/config/dashboardDefaults';
import { useConfigurations } from '@/shared/queries/configurations';
import { useVariables } from '@/shared/queries/variables';
import { ActionTypes, useDashboard } from '../DashboardContext';

/**
 * Load filters from data warehouse API and apply defaults
 * @param table Data warehouse table to reference in queries
 * @returns UseQueryResult objects for configurations and variables
 */
export const useInitialFilters = (table: string) => {
  const { dispatch } = useDashboard();

  const configurations = useConfigurations(table);
  const variables = useVariables(table);

  const defaultConfiguration = selectDefault(
    RETROSPECTIVE_DASHBOARD_DEFAULTS.preferredConfiguration,
    configurations.data ?? []
  );

  const defaultVariable = selectDefault(
    RETROSPECTIVE_DASHBOARD_DEFAULTS.preferredVariable,
    variables.data ?? []
  );

  useEffect(() => {
    if (!defaultConfiguration || !defaultVariable) {
      return;
    }

    dispatch({
      type: ActionTypes.INITIALIZE_FILTERS,
      payload: {
        configuration: defaultConfiguration,
        variable: defaultVariable,
      },
    });
  }, [defaultConfiguration, defaultVariable, dispatch]);

  return {
    configurations,
    variables,
  };
};
