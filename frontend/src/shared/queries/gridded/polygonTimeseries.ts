import { skipToken, useQueries, useQuery } from '@tanstack/react-query';

import { getPrimaryTimeseries } from '@/shared/api/timeseries';
import type { GriddedTimeseriesFilters } from '@/shared/types/gridded/timeseries';
import { parseUtcTime, shortestStep } from '@/shared/utils/dates';

import { DEFAULT_SPAN_STEPS } from './edr';
import { timestepsQueryOptions } from './timesteps';

type PolygonTimeseriesArgs = GriddedTimeseriesFilters & {
  locationId?: string;
  variable: string | null;
  // End of the default span: the map's date when the timeseries was loaded
  anchor?: string;
};

// Times are naive UTC, so shift in UTC and drop the zone again
const msBefore = (time: string, ms: number) =>
  new Date(parseUtcTime(time) - ms).toISOString().slice(0, 19);

// Mean areal timeseries of a polygon from the warehouse, one series per dataset. Hub writes
// analysis mean areal values to primary_timeseries.
export const usePolygonTimeseries = ({
  locationId,
  datasets,
  variable,
  start_date,
  end_date,
  anchor,
}: PolygonTimeseriesArgs) => {
  const useDefaultSpan = !start_date && !end_date;
  // Default span: DEFAULT_SPAN_STEPS of the datasets' shortest step, as for point queries
  const timesteps = useQueries({
    queries: datasets.map((ds) => ({
      ...timestepsQueryOptions(ds),
      enabled: useDefaultSpan && !!ds,
    })),
  });
  const step = Math.min(...timesteps.map((t) => shortestStep((t.data ?? []).map(parseUtcTime))));
  const spanMs = Number.isFinite(step) ? DEFAULT_SPAN_STEPS * step : null;
  const start = useDefaultSpan ? anchor && spanMs !== null && msBefore(anchor, spanMs) : start_date;
  const end = useDefaultSpan ? anchor : end_date;

  return useQuery({
    queryKey: ['gridded', 'polygonTimeseries', locationId, datasets, variable, start, end],
    queryFn:
      locationId && variable && datasets.length > 0 && (!useDefaultSpan || start)
        ? () =>
            getPrimaryTimeseries(locationId, {
              configuration: datasets,
              variable,
              start_date: start || undefined,
              end_date: end ?? undefined,
            })
        : skipToken,
  });
};
