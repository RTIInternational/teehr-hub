import type { FeatureCollection, Point } from 'geojson';

import { griddedApiCall } from './client';

export type EdrPointResponse = FeatureCollection<Point, EdrPointProps>;

type EdrPointProps = Record<string, unknown> & {
  time: string;
  lat: number;
  lon: number;
  longitude: number;
  latitude: number;
  spatial_ref: number;
};

export type EdrTimeseriesFilters = {
  datasetId: string | null;
  variable: string | null;
  lon?: number;
  lat?: number;
  timesteps: string[];
};

export type EdrTimeseriesResponse = string;

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

export const fetchGriddedEdrPoint = async (
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
  const path = `/api/datasets/${encodeURIComponent(datasetId + '_data')}/edr/position?${params.toString()}`;
  const data = await griddedApiCall<EdrPointResponse>(path);
  try {
    const properties = data?.features?.[0]?.properties ?? {};
    const value =
      properties[variable] ?? Object.values(properties).find((v) => typeof v === 'number');
    return value !== undefined ? value : null;
  } catch {
    return null;
  }
};

export const fetchGriddedEdrTimeseries = async (
  datasetId: string,
  variable: string,
  lon: number,
  lat: number,
  start: string,
  end: string
) => {
  const datetimeRange = start === end ? start : `${start}/${end}`;
  const params = new URLSearchParams({
    coords: `POINT(${lon} ${lat})`,
    'parameter-name': variable,
    datetime: datetimeRange,
    f: 'csv',
  });
  const path = `/api/datasets/${encodeURIComponent(datasetId + '_data')}/edr/position?${params.toString()}`;
  const csvText = await griddedApiCall<EdrTimeseriesResponse>(path, { raw: true });
  return parseTimeseriesCsv(csvText, variable);
};
