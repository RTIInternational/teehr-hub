import type { Feature, Point } from 'geojson';
import type { OgcLink } from './ogc';

export type MetricsFeature = Feature<Point, MetricsProperties>;

export type MetricsFilters = {
  configuration?: string;
  table?: string;
  variable?: string;
};

export type MetricsProperties = {
  primary_location_id: string;
  [key: string]: unknown;
};

export type MetricsResponse = {
  type: string;
  features: MetricsFeature[];
  links: OgcLink[];
};
