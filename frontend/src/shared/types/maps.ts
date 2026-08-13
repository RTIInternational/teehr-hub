import type { Feature, Point } from 'geojson';
import type { metricDisplay } from '@/shared/utils/utils';

export type InvalidFeature = {
  index: number;
  reason: string;
  feature: Feature<Point>;
};

export type LngLatTuple = [number, number];

export type MapFilters = {
  configuration?: string | null;
  variable?: string | null;
  threshold?: string;
  aggMethod?: string;
  leadTimeBin?: string;
  metricName?: MapMetric;
};

export type MapMetric = keyof typeof metricDisplay;

export type MapMetricClamped = {
  index: number;
  metric: MapMetric;
  original: number;
  clamped: number;
};

export type MapState = {
  mapFilters: MapFilters;
  mapLoaded: boolean;
};
