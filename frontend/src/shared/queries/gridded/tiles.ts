import { useQuery } from '@tanstack/react-query';

import { griddedApiService } from '@/services/griddedApi';

export const usePolygonLayers = () =>
  useQuery({
    queryKey: ['polygons'],
    queryFn: () => griddedApiService.discoverPolygonLayers(),
    select: (data) => data.items,
  });

const fetchTilesLegend = async (
  datasetId: string | null | undefined,
  variable: string | null | undefined,
  colorRamp: string,
  min: number,
  max: number
) => {
  if (!datasetId || !variable) {
    throw new Error('Dataset and variable required to retrieve the legend');
  }

  return griddedApiService.getTilesLegend(datasetId, variable, colorRamp, min, max);
};

export const useTilesLegend = (
  datasetId: string | null | undefined,
  variable: string | null | undefined,
  colorRamp: string,
  min: number,
  max: number
) =>
  useQuery({
    queryKey: ['gridded', datasetId, 'legend', variable, colorRamp, min, max],
    queryFn: () => fetchTilesLegend(datasetId, variable, colorRamp, min, max),
    enabled: !!datasetId && !!variable,
    // Keep the current bar while a new range or ramp loads, but never another variable's
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === datasetId && previousQuery?.queryKey[3] === variable
        ? previous
        : undefined,
  });
