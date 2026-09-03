import { useCallback } from 'react';

import { useNwmdDataFetching } from '../../../hooks/useNwmdDataFetching';

// Table names for nwmd dashboard
const TABLE_NAMES = ['nwmd_metrics_by_location'];

/**
 * Dashboard-specific hook for nwmd data
 * Handles the nwmd_metrics_by_location table specifically
 */
export const useNwmdData = () => {
  const { loadTimeseries, loadLeadTimeBinMetrics, loadLocationMetadata, ...otherHooks } =
    useNwmdDataFetching();

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

  return {
    ...otherHooks,
    loadTimeseries: loadNwmdTimeseries,
    loadLeadTimeBinMetrics: loadNwmdLeadTimeBinMetrics,
    loadLocationMetadata: loadNwmdLocationMetadata,
    tableName: TABLE_NAMES[0], // Default to location table
    tableNames: TABLE_NAMES,
  };
};
