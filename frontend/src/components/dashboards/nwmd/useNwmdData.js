import { useCallback } from 'react';
import { useNwmdDataFetching } from '../../../hooks/useNwmdDataFetching';

/**
 * Dashboard-specific hook for nwmd data
 * Handles the nwmd_metrics_by_location table specifically
 */
export const useNwmdData = () => {
  const { loadConfigurations, loadVariables, loadTableProperties, loadLocations, loadTimeseries, loadLocationMetrics, ...otherHooks } = useNwmdDataFetching();
  
  // Table names for nwmd dashboard
  const TABLE_NAMES = ['nwmd_metrics_by_location'];
  
  // Load configurations for nwmd metrics
  const loadNwmdConfigurations = useCallback(async () => {
    return loadConfigurations(TABLE_NAMES[0]); // Use location table for configurations
  }, [loadConfigurations]);
  
  // Load variables for nwmd metrics  
  const loadNwmdVariables = useCallback(async () => {
    return loadVariables(TABLE_NAMES[0]); // Use location table for variables
  }, [loadVariables]);
  
  // Load table properties for nwmd metrics
  const loadNwmdTableProperties = useCallback(async () => {
    return loadTableProperties(TABLE_NAMES);
  }, [loadTableProperties]);

  // Load locations with nwmd table context
  const loadNwmdLocations = useCallback(async (filters = {}) => {
    return loadLocations(filters, TABLE_NAMES[0]); // Use location table for map
  }, [loadLocations]);

  // Load timeseries with nwmd table context  
  const loadNwmdTimeseries = useCallback(async (filters = {}) => {
    return loadTimeseries({ ...filters, table: TABLE_NAMES[0] }); // Use location table for timeseries
  }, [loadTimeseries]);
  
  // Load location metrics with nwmd table context
  const loadNwmdLocationMetrics = useCallback(async (primaryLocationId, selectedTable = TABLE_NAMES[0]) => {
    return loadLocationMetrics(primaryLocationId, selectedTable);
  }, [loadLocationMetrics]);
  
  // Initialize all nwmd data
  const initializeNwmdData = useCallback(async () => {
    try {
      await Promise.all([
        loadNwmdConfigurations(),
        loadNwmdVariables(), 
        loadNwmdTableProperties()
      ]);
    } catch (error) {
      console.error('Failed to initialize nwmd data:', error);
      throw error;
    }
  }, [loadNwmdConfigurations, loadNwmdVariables, loadNwmdTableProperties]);
  
  return {
    ...otherHooks,
    loadConfigurations: loadNwmdConfigurations,
    loadVariables: loadNwmdVariables,
    loadTableProperties: loadNwmdTableProperties,
    loadLocations: loadNwmdLocations,
    loadTimeseries: loadNwmdTimeseries,
    loadLocationMetrics: loadNwmdLocationMetrics,
    initializeNwmdData: initializeNwmdData,
    tableName: TABLE_NAMES[0], // Default to location table
    tableNames: TABLE_NAMES
  };
};