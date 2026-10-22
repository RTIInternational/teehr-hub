import type { FeatureCollection, Point } from 'geojson';

import type { MetricsFilters } from '../types/metrics';
import { apiCallJson } from './client';
import { aliasMap } from './utils';

// API service object - OGC API compliant
// Metrics tables written before teehr 0.9 use primary_location_id,
// configuration_name and variable_name. Fill in the renamed columns so
// components read one set of names while tables are regenerated.
export const LEGACY_METRIC_COLUMNS: Record<string, string> = {
  location_id: 'primary_location_id',
  secondary_configuration_name: 'configuration_name',
  secondary_variable_name: 'variable_name',
};

export const withRenamedMetricColumns = (
  collection: FeatureCollection<Point>
): FeatureCollection<Point> => {
  for (const feature of collection.features ?? []) {
    const props = feature.properties;
    if (!props) continue;
    for (const [column, legacy] of Object.entries(LEGACY_METRIC_COLUMNS)) {
      if (props[column] === undefined && props[legacy] !== undefined) {
        props[column] = props[legacy];
      }
    }
  }
  return collection;
};

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

  return apiCallJson<FeatureCollection<Point>>(endpoint).then(withRenamedMetricColumns);
};
