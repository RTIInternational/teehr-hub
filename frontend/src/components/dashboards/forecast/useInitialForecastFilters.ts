import { useEffect } from 'react';
import { FORECAST_DASHBOARD_DEFAULTS, selectDefault } from '../../../config/dashboardDefaults';
import { ActionTypes, useForecastDashboard } from '../../../context/ForecastDashboardContext';
import { useConfigurations } from '../../../shared/queries/configurations';
import { useVariables } from '../../../shared/queries/variables';

export const useInitialForecastFilters = (table: string) => {
  const { dispatch } = useForecastDashboard();

  const configurations = useConfigurations(table);
  const variables = useVariables(table);
  useVariables('primary_timeseries'); // Pre-load primary variables

  const defaultConfiguration = selectDefault(
    FORECAST_DASHBOARD_DEFAULTS.preferredConfiguration,
    configurations.data ?? []
  );

  const defaultVariable = selectDefault(
    FORECAST_DASHBOARD_DEFAULTS.preferredVariable,
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
