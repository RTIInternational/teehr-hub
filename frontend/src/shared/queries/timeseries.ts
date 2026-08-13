import { useQuery } from '@tanstack/react-query';
import { apiService } from '@/services/api';
import { ISO_TO_DURATION_NAME, isTimestepVariable } from '@/utils/durationUtils';
import type { TimeseriesResponse, Timeseries, TimeseriesRequestFilters } from '../types/timeseries';

const fetchPrimaryTimeseries = async (filters: TimeseriesRequestFilters) => {
  const { primary_location_id, primary } = filters;
  const { variables, start_date, end_date, duration } = primary;

  if (!primary_location_id || !variables?.length) {
    throw new Error('Missing required parameters: primary_location_id and variables are required');
  }

  const hasTimestepVar = filters.primary.variables?.some(isTimestepVariable);
  const primaryDuration = hasTimestepVar ? duration : null;

  const primaryFilters = {
    variable: variables,
    start_date,
    end_date,
    ...(primaryDuration && { duration: primaryDuration }),
  };

  return await apiService
    .getPrimaryTimeseries(primary_location_id, primaryFilters)
    .then((results) =>
      results.map((series: Timeseries) => ({
        ...series,
        duration_token: primaryDuration ? ISO_TO_DURATION_NAME[primaryDuration] : null,
      }))
    );
};

const fetchSecondaryTimeseries = async (filters: TimeseriesRequestFilters) => {
  const { primary_location_id, secondary } = filters;
  const {
    configurations,
    variables,
    start_date,
    end_date,
    reference_start_date,
    reference_end_date,
  } = secondary;

  if (!primary_location_id || !configurations?.length || !variables?.length) {
    throw new Error(
      'Missing required parameters: primary_location_id, configurations, and variables are required'
    );
  }

  // Load secondary data with multi-value configuration filtering
  const secondaryFilters = {
    variable: variables,
    start_date,
    end_date,
    reference_start_date,
    reference_end_date,
    configuration: configurations,
  };

  return await apiService.getSecondaryTimeseries(primary_location_id, secondaryFilters);
};

export const usePrimaryTimeseries = (filters?: TimeseriesRequestFilters) =>
  useQuery<TimeseriesResponse>({
    queryKey: ['timeseries', 'primary', filters],
    queryFn: () => {
      if (!filters) {
        throw new Error('Filters are required to fetch timeseries');
      }
      return fetchPrimaryTimeseries(filters);
    },
    enabled: !!filters && !!filters.primary_location_id && !!filters.primary?.variables?.length,
  });

export const useSecondaryTimeseries = (filters?: TimeseriesRequestFilters) =>
  useQuery<TimeseriesResponse>({
    queryKey: ['timeseries', 'secondary', filters],
    queryFn: () => {
      if (!filters) {
        throw new Error('Filters are required to fetch timeseries');
      }
      return fetchSecondaryTimeseries(filters);
    },
    enabled:
      !!filters &&
      !!filters.primary_location_id &&
      !!filters.secondary?.configurations?.length &&
      !!filters.secondary?.variables?.length,
  });
