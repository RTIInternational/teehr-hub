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
