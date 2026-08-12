import { useCallback } from 'react';
import { useRetrospectiveDataFetching } from '../../../hooks/useRetrospectiveDataFetching';

/**
 * Dashboard-specific hook for retrospective simulation data
 * Handles the sim_metrics_by_location table specifically
 */
export const useRetrospectiveData = () => {
  const { loadConfigurations, loadVariables, ...otherHooks } = useRetrospectiveDataFetching();

  // Table name for retrospective dashboard
  const TABLE_NAME = 'sim_metrics_by_location';

  // Load configurations for simulation metrics
  const loadSimConfigurations = useCallback(async () => {
    return loadConfigurations(TABLE_NAME);
  }, [loadConfigurations]);

  // Load variables for simulation metrics
  const loadSimVariables = useCallback(async () => {
    return loadVariables(TABLE_NAME);
  }, [loadVariables]);

  // Initialize all retrospective data
  const initializeRetrospectiveData = useCallback(async () => {
    console.log('useRetrospectiveData: Starting initialization...');
    try {
      const results = await Promise.all([loadSimConfigurations(), loadSimVariables()]);
      console.log('useRetrospectiveData: Initialization completed successfully', results);
    } catch (error) {
      console.error('Failed to initialize retrospective data:', error);
      throw error;
    }
  }, [loadSimConfigurations, loadSimVariables]);

  return {
    ...otherHooks,
    loadConfigurations: loadSimConfigurations,
    loadVariables: loadSimVariables,
    initializeRetrospectiveData,
    tableName: TABLE_NAME,
  };
};
