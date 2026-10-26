import type { FeatureCollection, Point } from 'geojson';

import type { OgcLink } from '@/shared/api/ogc';

import { apiCallJson } from './client';
import { aliasMap } from './utils';

export type MetricsFilters = {
  [queryable: string]: string | null;
  configuration: string;
  table: string;
  variable: string;
};

export type MetricsProperties = {
  location_id: string;
  [key: string]: unknown;
};

export type MetricsFeature = {
  type: 'Feature';
  geometry: Point;
  properties: MetricsProperties;
};

export type MetricsResponse = {
  type: string;
  features: MetricsFeature[];
  links: OgcLink[];
};

// API service object - OGC API compliant
// Get metrics with filtering (OGC API - Features)
export const getMetrics = (filters: Partial<MetricsFilters> = {}) => {
  const params = new URLSearchParams();
  const table = filters.table || 'sim_metrics_by_location';

  const reservedKeys = ['table'];

  for (const key in filters) {
    if (reservedKeys.includes(key)) continue;
    const paramKey = aliasMap[key] || key;
    const filterValue = filters[key] === null ? 'null' : filters[key];
    if (filterValue) params.append(paramKey, filterValue);
  }

  const queryString = params.toString();
  const endpoint = queryString
    ? `/collections/${table}/items?${queryString}`
    : `/collections/${table}/items`;

  return apiCallJson<FeatureCollection<Point>>(endpoint);
};
