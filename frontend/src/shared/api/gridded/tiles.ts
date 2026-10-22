import type { TilesLegendResponse, VectorTilesResponse } from '@/shared/types/gridded/tiles';

import { GRIDDED_API_BASE_URL, griddedApiCall } from './client';

export const discoverPolygonLayers = () => griddedApiCall<VectorTilesResponse>('/api/vector-tiles');

// The archive is served by xpublish-api rather than object storage, so the
// bytes are covered by the same Keycloak token as every other call. Must be
// absolute: the pmtiles Protocol keys its registered sources by exact URL.
export const buildPmtilesUrl = (layerId: string) =>
  `${GRIDDED_API_BASE_URL}/api/vector-tiles/${encodeURIComponent(layerId)}.pmtiles`;

export const getTilesLegend = (
  datasetId: string,
  variable: string,
  colorRamp = 'raster/plasma',
  min = 0,
  max = 100
) => {
  const params = new URLSearchParams({
    variables: variable,
    style: colorRamp,
    colorscalerange: `${min},${max}`,
    belowmincolor: 'transparent',
    f: 'application/json',
  });
  return griddedApiCall<TilesLegendResponse>(
    `/api/datasets/${encodeURIComponent(datasetId)}/tiles/legend?${params.toString()}`
  );
};

// Note: {z}/{y}/{x} order (y before x) is required by TilesPlugin.
export const buildGriddedTileUrl = (
  datasetId: string,
  variable: string,
  timestep: string,
  colorRamp = 'raster/plasma',
  min = 0,
  max = 100
) => {
  const params = new URLSearchParams({
    variables: variable,
    style: colorRamp,
    colorscalerange: `${min},${max}`,
    belowmincolor: 'transparent',
    width: '256',
    height: '256',
    f: 'image/png',
    time: timestep,
  });
  return `${GRIDDED_API_BASE_URL}/api/datasets/${encodeURIComponent(datasetId)}/tiles/WebMercatorQuad/{z}/{y}/{x}?${params.toString()}`;
};
