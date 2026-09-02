import { useCallback } from 'react';

import { useNwmdDataFetching } from '../../../hooks/useNwmdDataFetching';

// Table names for nwmd dashboard
const TABLE_NAMES = ['nwmd_metrics_by_location'];

/**
 * Dashboard-specific hook for nwmd data
 * Handles the nwmd_metrics_by_location table specifically
 */
export const useNwmdData = () => {
  const {
    loadTableProperties,
    loadLocations,
    loadTimeseries,
    loadLeadTimeBinMetrics,
    loadLocationMetadata,
    ...otherHooks
  } = useNwmdDataFetching();

  // Load table properties for nwmd metrics
  const loadNwmdTableProperties = useCallback(async () => {
    return loadTableProperties(TABLE_NAMES);
  }, [loadTableProperties]);

  // Load locations with nwmd table context
  const loadNwmdLocations = useCallback(
    async (filters = {}) => {
      return loadLocations(filters, TABLE_NAMES[0]); // Use location table for map
    },
    [loadLocations]
  );

  // Load timeseries with nwmd table context
  const loadNwmdTimeseries = useCallback(
    async (filters = {}) => {
      return loadTimeseries({ ...filters, table: TABLE_NAMES[0] }); // Use location table for timeseries
    },
    [loadTimeseries]
  );

  const loadNwmdLocationMetadata = useCallback(
    async (primaryLocationId) => {
      return loadLocationMetadata(primaryLocationId);
    },
    [loadLocationMetadata]
  );

  const loadNwmdLeadTimeBinMetrics = useCallback(
    async (filters = {}) => {
      return loadLeadTimeBinMetrics(filters, TABLE_NAMES[0]);
    },
    [loadLeadTimeBinMetrics]
  );

  // Initialize all nwmd data
  const initializeNwmdData = useCallback(async () => {
    try {
      await loadNwmdTableProperties();
    } catch (error) {
      console.error('Failed to initialize nwmd data:', error);
      throw error;
    }
  }, [loadNwmdTableProperties]);

  return {
    ...otherHooks,
    loadTableProperties: loadNwmdTableProperties,
    loadLocations: loadNwmdLocations,
    loadTimeseries: loadNwmdTimeseries,
    loadLeadTimeBinMetrics: loadNwmdLeadTimeBinMetrics,
    loadLocationMetadata: loadNwmdLocationMetadata,
    initializeNwmdData: initializeNwmdData,
    tableName: TABLE_NAMES[0], // Default to location table
    tableNames: TABLE_NAMES,
  };
};
