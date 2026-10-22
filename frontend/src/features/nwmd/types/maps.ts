import type { MetricsFilters } from '@/shared/api/metrics';
import type { MapMetric } from '@/shared/types/maps';

export type AltHypothesisOperator = '=0' | '!=0' | '>0' | '<0' | '>1' | '<1';

export type NwmdMapFilters = Partial<MetricsFilters> & {
  waterYear?: string | null;
  quarter?: string | null;
  threshold?: string | null;
  aggMethod?: string | null;
  leadTimeBin?: string | null;
  metricName?: MapMetric | null;
  altHypothesis95?: AltHypothesisOperator | null;
};

export type ViewportBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};
