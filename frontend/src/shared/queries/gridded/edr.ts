import { useQuery } from '@tanstack/react-query';
import { griddedApiService } from '@/services/griddedApi';
import type { EdrTimeseriesFilters, TimeseriesData } from '@/shared/types/gridded/edr';

const fetchEdrTimeseries = async (filters: EdrTimeseriesFilters) => {
  if (!filters.datasetId || !filters.variable || !filters.lon || !filters.lat) {
    throw new Error('Missing required parameters: datasetId, variable, lon, and lat are required');
  }

  return await griddedApiService.fetchGriddedEdrTimeseries(
    filters.datasetId,
    filters.variable,
    filters.lon,
    filters.lat,
    filters.timesteps
  );
};

export const useEdrTimeseries = (filters: EdrTimeseriesFilters) =>
  useQuery({
    queryKey: ['gridded', 'edrTimeseries', filters],
    queryFn: () => fetchEdrTimeseries(filters),
    enabled:
      !!filters.datasetId &&
      !!filters.variable &&
      !!filters.lon &&
      !!filters.lat &&
      filters.timesteps.length > 0,
    select: (data) =>
      ({
        ...data,
        lon: filters.lon!,
        lat: filters.lat!,
        variable: filters.variable!,
      }) as TimeseriesData,
  });
