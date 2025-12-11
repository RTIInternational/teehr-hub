import { useCallback } from 'react';
import { useForecastDataFetching } from '../../../hooks/useForecastDataFetching';

/**
 * Dashboard-specific hook for forecast data
 * Handles the forecast_metrics_by_location table specifically
 */
export const useForecastData = () => {
  const { loadConfigurations, loadVariables, loadMetricNames, loadLocations, loadTimeseries, ...otherHooks } = useForecastDataFetching();
  
  // Table name for forecast dashboard
  const TABLE_NAME = 'fcst_metrics_by_location';
  
  // Load configurations for forecast metrics
  const loadForecastConfigurations = useCallback(async () => {
    return loadConfigurations(TABLE_NAME);
  }, [loadConfigurations]);
  
  // Load variables for forecast metrics  
  const loadForecastVariables = useCallback(async () => {
    return loadVariables(TABLE_NAME);
  }, [loadVariables]);
  
  // Load metric names for forecast metrics
  const loadForecastMetricNames = useCallback(async () => {
    return loadMetricNames(TABLE_NAME);
  }, [loadMetricNames]);

  // Load locations with forecast table context
  const loadForecastLocations = useCallback(async (filters = {}) => {
    return loadLocations(filters, TABLE_NAME);
  }, [loadLocations]);

  // Load timeseries with forecast table context  
  const loadForecastTimeseries = useCallback(async (filters = {}) => {
    return loadTimeseries({ ...filters, table: TABLE_NAME });
  }, [loadTimeseries]);
  
  // Initialize all forecast data
  const initializeForecastData = useCallback(async () => {
    try {
      await Promise.all([
        loadForecastConfigurations(),
        loadForecastVariables(), 
        loadForecastMetricNames()
      ]);
    } catch (error) {
      console.error('Failed to initialize forecast data:', error);
      throw error;
    }
  }, [loadForecastConfigurations, loadForecastVariables, loadForecastMetricNames]);
  
  return {
    ...otherHooks,
    loadConfigurations: loadForecastConfigurations,
    loadVariables: loadForecastVariables,
    loadMetricNames: loadForecastMetricNames,
    loadLocations: loadForecastLocations,
    loadTimeseries: loadForecastTimeseries,
    initializeForecastData,
    tableName: TABLE_NAME
  };
};