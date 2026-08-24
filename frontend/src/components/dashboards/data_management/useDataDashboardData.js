import { useCallback } from 'react';
import { useDataDashboardFetching } from '../../../hooks/useDataDashboardFetching';

export const useDataDashboardData = () => {
  const { loadLocations, loadConfigurationsTable, selectLocation } = useDataDashboardFetching();

  // Initialize all data dashboard data
  const initializeDataDashboard = useCallback(async () => {
    console.log('useDataDashboardData: Starting initialization...');
    const results = await Promise.allSettled([
      loadLocations(),
      loadConfigurationsTable()
    ]);
    results.forEach((result, i) => {
      if (result.status === 'rejected') {
        console.error(`useDataDashboardData: Init task ${i} failed:`, result.reason);
      }
    });
    console.log('useDataDashboardData: Initialization completed');
  }, [loadLocations, loadConfigurationsTable]);

  return {
    loadLocations,
    loadConfigurations: loadConfigurationsTable,
    selectLocation,
    initializeDataDashboard
  };
};
