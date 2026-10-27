import { useQueries } from '@tanstack/react-query';

import { fetchGriddedEdrTimeseries } from '@/shared/api/gridded/edr';
import type { DatasetTimeseries } from '@/shared/types/gridded/edr';
import type { GriddedTimeseriesFilters } from '@/shared/types/gridded/timeseries';

import { timestepsQueryOptions } from './timesteps';
import { variablesQueryOptions } from './variables';

// Timesteps in the default span, and the most a chosen span may cover: 30 days of hourly data
export const MAX_NUM_TIMESTEPS = 720;

type EdrTimeseriesArgs = GriddedTimeseriesFilters & {
  preferredVariable: string | null;
  lon?: number;
  lat?: number;
  // End of the default span: the map's date when the point was clicked
  anchor?: string;
};

type SeriesPlan = { variable: string | null; start?: string; end?: string; skipped?: string };

// datetime-local values omit seconds; dataset timestamps include them
const withSeconds = (value: string) => (value.length === 16 ? `${value}:00` : value);

const planSeries = (
  datasetId: string,
  variables: string[],
  timesteps: string[],
  preferredVariable: string | null,
  startDate: string | null,
  endDate: string | null,
  anchor: string | undefined
): SeriesPlan => {
  const variable =
    preferredVariable && variables.includes(preferredVariable)
      ? preferredVariable
      : (variables[0] ?? null);
  if (timesteps.length === 0) return { variable };

  const first = timesteps[0];
  const last = timesteps[timesteps.length - 1];
  if (!startDate && !endDate) {
    const upTo = anchor ? timesteps.filter((t) => t <= anchor) : timesteps;
    if (upTo.length === 0)
      return { variable, skipped: `${datasetId}: no data on or before ${anchor}` };
    return {
      variable,
      start: upTo[Math.max(0, upTo.length - MAX_NUM_TIMESTEPS)],
      end: upTo[upTo.length - 1],
    };
  }

  const start = startDate ? withSeconds(startDate) : first;
  const end = endDate ? withSeconds(endDate) : last;
  const steps = timesteps.filter((t) => t >= start && t <= end).length;
  if (steps === 0) return { variable, skipped: `${datasetId}: no data in the selected span` };
  if (steps > MAX_NUM_TIMESTEPS) {
    return {
      variable,
      skipped: `${datasetId}: span covers ${steps.toLocaleString()} timesteps; max ${MAX_NUM_TIMESTEPS.toLocaleString()}`,
    };
  }
  return { variable, start, end };
};

export const useEdrTimeseries = ({
  datasets,
  preferredVariable,
  lon,
  lat,
  start_date,
  end_date,
  anchor,
}: EdrTimeseriesArgs): DatasetTimeseries[] => {
  const variables = useQueries({ queries: datasets.map((ds) => variablesQueryOptions(ds)) });
  const timesteps = useQueries({ queries: datasets.map((ds) => timestepsQueryOptions(ds)) });
  const plans = datasets.map((ds, i) =>
    planSeries(
      ds,
      variables[i].data ?? [],
      timesteps[i].data ?? [],
      preferredVariable,
      start_date,
      end_date,
      anchor
    )
  );

  const series = useQueries({
    queries: datasets.map((ds, i) => {
      const { variable, start, end } = plans[i];
      return {
        queryKey: ['gridded', 'edrTimeseries', ds, variable, lon, lat, start, end],
        queryFn: () => fetchGriddedEdrTimeseries(ds, variable!, lon!, lat!, start!, end!),
        enabled: variable != null && start != null && end != null && lon != null && lat != null,
      };
    }),
  });

  return datasets.map((datasetId, i) => ({
    datasetId,
    variable: plans[i].variable,
    data: series[i].data,
    error: (variables[i].error ?? timesteps[i].error ?? series[i].error)?.message,
    skipped: plans[i].skipped,
    isLoading: variables[i].isLoading || timesteps[i].isLoading || series[i].isLoading,
  }));
};
