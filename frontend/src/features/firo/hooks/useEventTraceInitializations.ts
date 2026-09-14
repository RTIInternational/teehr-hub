import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';

export type EventTraceInitializationsFilters = {
  primaryLocationId: string | null;
  configurationName?: string | null;
  variableName?: string | null;
  threshold?: string | null;
  eventId?: string | null;
  leadTimeHours?: number | null;
};

export type EventTraceInitializationsResponse = {
  primary_location_id: string;
  configuration_name: string;
  variable_name: string;
  threshold: string;
  event_id: string;
  lead_time_hours: number;
  event_start: string;
  event_end: string;
  expanded_event_start: string;
  expanded_event_end: string;
  available_initialization_datetimes: string[];
  default_initialization_datetime: string;
};

export const useEventTraceInitializations = (filters: EventTraceInitializationsFilters) => {
  const { primaryLocationId, configurationName, variableName, threshold, eventId, leadTimeHours } =
    filters;

  return useQuery<EventTraceInitializationsResponse>({
    queryKey: [
      'firo',
      'eventTraceInitializations',
      primaryLocationId,
      configurationName,
      variableName,
      threshold,
      eventId,
      leadTimeHours,
    ],
    queryFn: () =>
      apiService.getEventTraceInitializations({
        primary_location_id: primaryLocationId,
        configuration_name: configurationName ?? null,
        variable_name: variableName ?? null,
        threshold: threshold ?? null,
        event_id: eventId ?? null,
        lead_time_hours: leadTimeHours ?? null,
      }),
    enabled:
      !!primaryLocationId &&
      !!configurationName &&
      !!variableName &&
      !!threshold &&
      !!eventId &&
      !!leadTimeHours,
    staleTime: Infinity,
  });
};

export type TracePoint = {
  value_time: string;
  value: number;
};

export type EnsembleMemberTrace = {
  member: string;
  values: TracePoint[];
};

export type EventTraceDataResponse = {
  primary_location_id: string;
  configuration_name: string;
  variable_name: string;
  threshold: string;
  initialization_datetime: string;
  window_start: string;
  window_end: string;
  observed: {
    pre_initialization: TracePoint[];
    post_initialization: TracePoint[];
  };
  forecast_members: EnsembleMemberTrace[];
  forecast_percentiles: {
    p10: TracePoint[];
    p50: TracePoint[];
    p90: TracePoint[];
  };
};

export type EventTraceDataFilters = {
  primaryLocationId: string | null;
  configurationName?: string | null;
  variableName?: string | null;
  threshold?: string | null;
  windowStart?: string | null;
  windowEnd?: string | null;
  initializationTime?: string | null;
};

export const useEventTraceData = (filters: EventTraceDataFilters) => {
  const {
    primaryLocationId,
    configurationName,
    variableName,
    threshold,
    windowStart,
    windowEnd,
    initializationTime,
  } = filters;

  return useQuery<EventTraceDataResponse>({
    queryKey: [
      'firo',
      'eventTraceData',
      primaryLocationId,
      configurationName,
      variableName,
      threshold,
      windowStart,
      windowEnd,
      initializationTime,
    ],
    queryFn: () =>
      apiService.getEventTraceData({
        primary_location_id: primaryLocationId,
        configuration_name: configurationName ?? null,
        variable_name: variableName ?? null,
        threshold: threshold ?? null,
        window_start: windowStart ?? null,
        window_end: windowEnd ?? null,
        initialization_time: initializationTime ?? null,
      }),
    enabled:
      !!primaryLocationId &&
      !!configurationName &&
      !!variableName &&
      !!threshold &&
      !!windowStart &&
      !!windowEnd &&
      !!initializationTime,
    staleTime: Infinity,
  });
};
