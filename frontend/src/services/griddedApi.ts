// Gridded / xpublish API service backed by VITE_XPUBLISH_API_BASE_URL
import { ensureFreshToken } from '@/features/auth/keycloak';
import type { DatasetsResponse } from '@/shared/types/gridded/datasets';
import type { EdrPointResponse, EdrTimeseriesResponse } from '@/shared/types/gridded/edr';
import type { VectorTilesResponse } from '@/shared/types/gridded/tiles';
import type { TimestepsResponse } from '@/shared/types/gridded/timesteps';
import type { VariableAttrsResponse } from '@/shared/types/gridded/variableAttrs';
import type { VariablesResponse } from '@/shared/types/gridded/variables';

export const GRIDDED_API_BASE_URL =
  import.meta.env.VITE_XPUBLISH_API_BASE_URL || 'http://127.0.0.1:8001';

export const MAX_TIMESERIES_POINTS = 365;

type GriddedApiCall = {
  (path: string, options?: { raw: true }): Promise<string>;
  <T>(path: string, options?: { raw?: false }): Promise<T>;
  <T>(path: string, options: { raw: boolean }): Promise<string | T>;
};

const griddedApiCall: GriddedApiCall = async <T>(path: string, { raw = false } = {}) => {
  const url = `${GRIDDED_API_BASE_URL}${path}`;
  const token = await ensureFreshToken();
  const headers: HeadersInit = { Accept: raw ? 'text/csv' : 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Gridded API error: ${response.status} ${response.statusText}`);
  }
  return raw ? response.text() : (response.json() as T);
};

function parseTimeseriesCsv(csvText: string, variable: string) {
  const lines = csvText
    .trim()
    .split('\n')
    .filter((l) => l.trim());
  if (lines.length < 2) return { times: [], values: [] };
  const headers = lines[0].split(',').map((h) => h.trim().replace(/^["']|["']$/g, ''));
  let timeColIdx = -1;
  for (const name of ['datetime', 'time', 'date']) {
    timeColIdx = headers.findIndex((h) => h.toLowerCase() === name);
    if (timeColIdx !== -1) break;
  }
  const varColIdx = headers.findIndex((h) => h === variable);
  if (varColIdx === -1) throw new Error(`Variable '${variable}' not found in timeseries response`);
  const times = [];
  const values = [];
  for (const line of lines.slice(1)) {
    const cols = line.split(',').map((c) => c.trim().replace(/^["']|["']$/g, ''));
    const val = parseFloat(cols[varColIdx]);
    if (Number.isFinite(val)) {
      times.push(timeColIdx !== -1 ? cols[timeColIdx] : '');
      values.push(val);
    }
  }
  return { times, values };
}

export const griddedApiService = {
  getGriddedDatasets: () => griddedApiCall<DatasetsResponse>('/api/dataset-keys'),

  discoverPolygonLayers: () => griddedApiCall<VectorTilesResponse>('/api/vector-tiles'),

  // The archive is served by xpublish-api rather than object storage, so the
  // bytes are covered by the same Keycloak token as every other call. Must be
  // absolute: the pmtiles Protocol keys its registered sources by exact URL.
  buildPmtilesUrl: (layerId: string) =>
    `${GRIDDED_API_BASE_URL}/api/vector-tiles/${encodeURIComponent(layerId)}.pmtiles`,

  getGriddedVariables: (datasetId: string) =>
    griddedApiCall<VariablesResponse>(`/api/dataset-variables/${encodeURIComponent(datasetId)}`),

  getGriddedTimesteps: (datasetId: string) =>
    griddedApiCall<TimestepsResponse>(`/api/datasets/${encodeURIComponent(datasetId)}/coords/time`),

  getGriddedVariableAttrs: (datasetId: string) =>
    griddedApiCall<VariableAttrsResponse>(
      `/api/datasets/${encodeURIComponent(datasetId)}/variable-attrs`
    ),

  // Note: {z}/{y}/{x} order (y before x) is required by TilesPlugin.
  buildGriddedTileUrl: (
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
  },

  fetchGriddedEdrPoint: async (
    datasetId: string,
    variable: string,
    timestep: string,
    lon: number,
    lat: number
  ) => {
    const params = new URLSearchParams({
      coords: `POINT(${lon} ${lat})`,
      'parameter-name': variable,
      datetime: timestep,
      f: 'geojson',
    });
    const path = `/api/datasets/${encodeURIComponent(datasetId + '_raw_data')}/edr/position?${params.toString()}`;
    const data = await griddedApiCall<EdrPointResponse>(path);
    try {
      const properties = data?.features?.[0]?.properties ?? {};
      const value =
        properties[variable] ?? Object.values(properties).find((v) => typeof v === 'number');
      return value !== undefined ? value : null;
    } catch {
      return null;
    }
  },

  fetchGriddedEdrTimeseries: async (
    datasetId: string,
    variable: string,
    lon: number,
    lat: number,
    timesteps: string[],
    maxPoints = MAX_TIMESERIES_POINTS
  ) => {
    const slice = maxPoints > 0 ? timesteps.slice(0, maxPoints) : timesteps;
    if (slice.length === 0) throw new Error('No timesteps available for timeseries query');
    const datetimeRange = slice.length === 1 ? slice[0] : `${slice[0]}/${slice[slice.length - 1]}`;
    const params = new URLSearchParams({
      coords: `POINT(${lon} ${lat})`,
      'parameter-name': variable,
      datetime: datetimeRange,
      f: 'csv',
    });
    const path = `/api/datasets/${encodeURIComponent(datasetId + '_raw_data')}/edr/position?${params.toString()}`;
    const csvText = await griddedApiCall<EdrTimeseriesResponse>(path, { raw: true });
    return parseTimeseriesCsv(csvText, variable);
  },
};
