import { useCallback } from 'react';
import { useForecastDataFetching } from '../../../hooks/useForecastDataFetching';

/**
 * Dashboard-specific hook for forecast data
 * Handles the forecast_metrics_by_location table specifically
 */
export const useForecastData = () => {
  const { loadConfigurations, loadVariables, loadPrimaryVariables, loadLocations, ...otherHooks } =
    useForecastDataFetching();

  // Table names for forecast dashboard
  const TABLE_NAMES = ['fcst_metrics_by_location', 'fcst_metrics_by_lead_time_bins'];

  // Load configurations for forecast metrics
  const loadForecastConfigurations = useCallback(async () => {
    return loadConfigurations(TABLE_NAMES[0]); // Use location table for configurations
  }, [loadConfigurations]);

  // Load variables for forecast metrics
  const loadForecastVariables = useCallback(async () => {
    return loadVariables(TABLE_NAMES[0]); // Use location table for variables
  }, [loadVariables]);

  // Load locations with forecast table context
  const loadForecastLocations = useCallback(
    async (filters = {}) => {
      return loadLocations(filters, TABLE_NAMES[0]); // Use location table for map
    },
    [loadLocations]
  );

  // Initialize all forecast data
  const initializeForecastData = useCallback(async () => {
    try {
      await Promise.all([
        loadForecastConfigurations(),
        loadForecastVariables(),
        loadPrimaryVariables(),
      ]);
    } catch (error) {
      console.error('Failed to initialize forecast data:', error);
      throw error;
    }
  }, [loadForecastConfigurations, loadForecastVariables, loadPrimaryVariables]);

  return {
    ...otherHooks,
    loadConfigurations: loadForecastConfigurations,
    loadVariables: loadForecastVariables,
    loadLocations: loadForecastLocations,
    initializeForecastData,
    tableName: TABLE_NAMES[0], // Default to location table
    tableNames: TABLE_NAMES,
  };
};
