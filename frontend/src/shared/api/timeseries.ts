import type { OgcResponse } from '../types/ogc';
import { groupPrimaryTimeseriesItems, groupSecondaryTimeseriesItems } from '../utils/timeseries';
import { apiCallJson } from './client';
import { normalizeEndpoint } from './utils';

export type PrimaryTimeseriesRequestFilters = {
  start_date?: string;
  end_date?: string;
  variable?: string | string[];
  configuration?: string | string[];
  duration?: string;
  limit?: number;
};

export type SecondaryTimeseriesRequestFilters = PrimaryTimeseriesRequestFilters & {
  reference_start_date?: string;
  reference_end_date?: string;
};

export type TimeseriesItem = {
  series_type: string;
  primary_location_id: string;
  secondary_location_id?: string;
  member?: string;
  reference_time: null;
  configuration_name: string;
  variable_name: string;
  unit_name: string;
  value_time: string;
  value: number;
  created_at: string;
  updated_at: string;
};

export type TimeseriesResponse = OgcResponse<TimeseriesItem>;

// Helper to format ISO 8601 datetime interval
export const formatDatetimeInterval = (startDate?: string, endDate?: string) => {
  if (!startDate && !endDate) return null;
  const start = startDate || '..';
  const end = endDate || '..';
  return `${start}/${end}`;
};

// Get primary timeseries (simple JSON array format)
export const getPrimaryTimeseries = async (
  primaryLocationId: string,
  filters: PrimaryTimeseriesRequestFilters = {}
) => {
  const params = new URLSearchParams();
  params.append('primary_location_id', primaryLocationId);

  // Use ISO 8601 datetime interval
  const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
  if (datetime) params.append('datetime', datetime);

  if (Array.isArray(filters.variable)) {
    filters.variable.forEach((variable) => {
      if (variable) params.append('variable_name', variable);
    });
  } else if (filters.variable) {
    params.append('variable_name', filters.variable);
  }

  if (Array.isArray(filters.configuration)) {
    filters.configuration.forEach((configuration) => {
      if (configuration) params.append('configuration_name', configuration);
    });
  } else if (filters.configuration) {
    params.append('configuration_name', filters.configuration);
  }
  if (filters.duration) params.append('timestep_duration', filters.duration);

  params.append('f', 'json');
  if (Number.isFinite(filters.limit)) {
    params.append('limit', Math.max(1, Number(filters.limit)).toString());
  }

  let nextEndpoint: string | null = `/collections/primary_timeseries/items?${params.toString()}`;
  const allItems = [];

  while (nextEndpoint) {
    const response: TimeseriesResponse | null = await apiCallJson<TimeseriesResponse>(nextEndpoint);
    const pageItems = Array.isArray(response?.items) ? response.items : [];
    allItems.push(...pageItems);

    const nextHref: string | undefined = response?.links?.find((link) => link.rel === 'next')?.href;
    nextEndpoint = nextHref ? normalizeEndpoint(nextHref) : null;
  }

  return groupPrimaryTimeseriesItems(allItems);
};

// Get secondary timeseries (simple JSON array format)
export const getSecondaryTimeseries = async (
  primaryLocationId: string,
  filters: SecondaryTimeseriesRequestFilters = {}
) => {
  const params = new URLSearchParams();
  params.append('primary_location_id', primaryLocationId);

  // Use ISO 8601 datetime interval for value_time
  const datetime = formatDatetimeInterval(filters.start_date, filters.end_date);
  if (datetime) params.append('datetime', datetime);

  // Use ISO 8601 datetime interval for reference_time
  const refDatetime = formatDatetimeInterval(
    filters.reference_start_date,
    filters.reference_end_date
  );
  if (refDatetime) params.append('reference_time', refDatetime);

  if (Array.isArray(filters.configuration)) {
    filters.configuration.forEach((configuration) => {
      if (configuration) params.append('configuration_name', configuration);
    });
  } else if (filters.configuration) {
    params.append('configuration_name', filters.configuration);
  }

  if (Array.isArray(filters.variable)) {
    filters.variable.forEach((variable) => {
      if (variable) params.append('variable_name', variable);
    });
  } else if (filters.variable) {
    params.append('variable_name', filters.variable);
  }
  if (filters.duration) params.append('timestep_duration', filters.duration);

  // Use paged JSON retrieval so we can follow next links and fetch all rows,
  // then regroup into the historical timeseries response shape expected by the UI.
  params.append('f', 'json');
  if (Number.isFinite(filters.limit)) {
    params.append('limit', Math.max(1, Number(filters.limit)).toString());
  }

  let nextEndpoint: string | null = `/collections/secondary_timeseries/items?${params.toString()}`;
  const allItems = [];

  while (nextEndpoint) {
    const response: TimeseriesResponse | null = await apiCallJson<TimeseriesResponse>(nextEndpoint);
    const pageItems = Array.isArray(response?.items) ? response.items : [];
    allItems.push(...pageItems);

    const nextHref: string | undefined = response?.links?.find((link) => link.rel === 'next')?.href;
    nextEndpoint = nextHref ? normalizeEndpoint(nextHref) : null;
  }
  const groupedSecondaryItems = groupSecondaryTimeseriesItems(allItems);
  return groupedSecondaryItems;
};
