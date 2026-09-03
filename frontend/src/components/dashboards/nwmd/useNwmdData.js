import { useCallback } from 'react';

import { useNwmdDataFetching } from '../../../hooks/useNwmdDataFetching';

// Table names for nwmd dashboard
const TABLE_NAMES = ['nwmd_metrics_by_location'];

/**
 * Dashboard-specific hook for nwmd data
 * Handles the nwmd_metrics_by_location table specifically
 */
export const useNwmdData = () => {
  const { loadLocationMetadata, ...otherHooks } = useNwmdDataFetching();

  const loadNwmdLocationMetadata = useCallback(
    async (primaryLocationId) => {
      return loadLocationMetadata(primaryLocationId);
    },
    [loadLocationMetadata]
  );

  return {
    ...otherHooks,
    loadLocationMetadata: loadNwmdLocationMetadata,
    tableName: TABLE_NAMES[0], // Default to location table
    tableNames: TABLE_NAMES,
  };
};
