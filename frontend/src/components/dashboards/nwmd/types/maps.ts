import type { MetricsFilters } from '@/shared/types/metrics';

type AltHypothesisOperator = '=0' | '!=0' | '>0' | '<0' | '>1' | '<1';

export type NwmdMapFilters = Partial<MetricsFilters> & {
  quarter?: string | null;
  threshold?: string | null;
  aggMethod?: string | null;
  leadTimeBin?: string | null;
  metricName?: string | null;
  altHypothesis95?: AltHypothesisOperator | null;
};

export type ViewportBounds = {
  west: number;
  south: number;
  east: number;
  north: number;
};
