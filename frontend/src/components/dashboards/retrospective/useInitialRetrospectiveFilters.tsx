import { useEffect } from 'react';
import { RETROSPECTIVE_DASHBOARD_DEFAULTS, selectDefault } from '../../../config/dashboardDefaults';
import {
  ActionTypes,
  useRetrospectiveDashboard,
} from '../../../context/RetrospectiveDashboardContext';
import { useConfigurations } from '../../../shared/queries/configurations';
import { useVariables } from '../../../shared/queries/variables';

export const useInitialRetrospectiveFilters = (table: string) => {
  const { dispatch } = useRetrospectiveDashboard();

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
