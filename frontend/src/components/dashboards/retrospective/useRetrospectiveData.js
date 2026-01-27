import { useCallback } from 'react';
import { useRetrospectiveDataFetching } from '../../../hooks/useRetrospectiveDataFetching';

/**
 * Dashboard-specific hook for retrospective simulation data
 * Handles the sim_metrics_by_location table specifically
 */
export const useRetrospectiveData = () => {
  const { loadConfigurations, loadVariables, loadTableProperties, loadLocations, loadTimeseries, loadLocationMetrics, ...otherHooks } = useRetrospectiveDataFetching();
  
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
  
  // Load table properties for simulation metrics
  const loadSimTableProperties = useCallback(async () => {
    return loadTableProperties([TABLE_NAME]);
  }, [loadTableProperties]);

  // Load locations with retrospective table context
  const loadSimLocations = useCallback(async (filters = {}) => {
    return loadLocations(filters, TABLE_NAME);
  }, [loadLocations]);

  // Load timeseries with retrospective table context  
  const loadSimTimeseries = useCallback(async (filters = {}) => {
    return loadTimeseries({ ...filters, table: TABLE_NAME });
  }, [loadTimeseries]);
  
  // Load location metrics with retrospective table context
  const loadSimLocationMetrics = useCallback(async (primaryLocationId) => {
    return loadLocationMetrics(primaryLocationId, TABLE_NAME);
  }, [loadLocationMetrics]);
  
  // Initialize all retrospective data
  const initializeRetrospectiveData = useCallback(async () => {
    console.log('useRetrospectiveData: Starting initialization...');
    try {
      const results = await Promise.all([
        loadSimConfigurations(),
        loadSimVariables(), 
        loadSimTableProperties()
      ]);
      console.log('useRetrospectiveData: Initialization completed successfully', results);
    } catch (error) {
      console.error('Failed to initialize retrospective data:', error);
      throw error;
    }
  }, [loadSimConfigurations, loadSimVariables, loadSimTableProperties]);
  
  return {
    ...otherHooks,
    loadConfigurations: loadSimConfigurations,
    loadVariables: loadSimVariables,
    loadTableProperties: loadSimTableProperties,
    loadLocations: loadSimLocations,
    loadTimeseries: loadSimTimeseries,
    loadLocationMetrics: loadSimLocationMetrics,
    initializeRetrospectiveData,
    tableName: TABLE_NAME
  };
};