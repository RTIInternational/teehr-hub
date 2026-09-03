import type { MapMetric } from '@/shared/types/maps';

type CdfPlot = {
  metricName: MapMetric;
};

export type CdfPlots = {
  [plotId: string]: CdfPlot;
};
