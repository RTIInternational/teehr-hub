import { useMemo, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Spinner from 'react-bootstrap/Spinner';

import { useDistinctValues } from '@/shared/queries/distinctValues';

import { useEventHeatmap } from '../hooks/useEventHeatmap';
import { useEventRankings } from '../hooks/useEventRankings';
import { useFiroDashboardStore } from '../store';
import TopEventsHeatmap, {
  type TopEventSummary,
  type TopEventsHeatmapMetric,
} from './TopEventsHeatmap';

const EVENT_TABLE = 'event_rankings';
const ALL_THRESHOLDS = 'all';

const METRIC_OPTIONS: Array<{ key: TopEventsHeatmapMetric; label: string }> = [
  { key: 'pearson_correlation', label: 'PCC' },
  { key: 'root_mean_square_error', label: 'RMSE' },
  { key: 'relative_bias', label: 'Bias' },
];

const toNumber = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const lower = trimmed.toLowerCase();
    if (lower === 'null' || lower === 'none' || lower === 'nan') return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const intervalStartDate = (eventId: string): string => {
  const match = eventId.match(/^(\d{4}-\d{2}-\d{2})/);
  return match?.[1] ?? eventId;
};

export const TopEventsSection = () => {
  const selectedLocation = useFiroDashboardStore((s) => s.selectedLocation);
  const selectedConfigurationName = useFiroDashboardStore((s) => s.selectedConfigurationName);
  const selectedVariableName = useFiroDashboardStore((s) => s.selectedVariableName);

  const [threshold, setThreshold] = useState<string>(ALL_THRESHOLDS);
  const [topN, setTopN] = useState<number>(10);
  const [metricKey, setMetricKey] = useState<TopEventsHeatmapMetric>('root_mean_square_error');
  const [heatmapExpanded, setHeatmapExpanded] = useState(false);

  const thresholdValues = useDistinctValues(EVENT_TABLE, 'threshold');

  const hasAllThresholdOption = useMemo(
    () =>
      (thresholdValues.data ?? []).some(
        (value) => value === null || value === 'null' || value === 'None'
      ),
    [thresholdValues.data]
  );

  const thresholdOptions = useMemo(
    () =>
      (thresholdValues.data ?? []).filter(
        (value) => value !== null && value !== 'null' && value !== 'None'
      ),
    [thresholdValues.data]
  );

  const effectiveThreshold =
    threshold === ALL_THRESHOLDS && !hasAllThresholdOption
      ? (thresholdOptions[0] ?? null)
      : threshold === ALL_THRESHOLDS
        ? null
        : threshold;

  const rankingsQuery = useEventRankings({
    primaryLocationId: selectedLocation?.primary_location_id ?? null,
    configurationName: selectedConfigurationName,
    variableName: selectedVariableName,
    threshold: effectiveThreshold,
  });

  const heatmapQuery = useEventHeatmap({
    primaryLocationId: selectedLocation?.primary_location_id ?? null,
    configurationName: selectedConfigurationName,
    variableName: selectedVariableName,
    threshold: effectiveThreshold,
  });

  const selectedThresholdValue =
    threshold === ALL_THRESHOLDS && !hasAllThresholdOption
      ? (thresholdOptions[0] ?? ALL_THRESHOLDS)
      : threshold;

  const rankedEvents = useMemo<TopEventSummary[]>(() => {
    const rows = rankingsQuery.data ?? [];
    const byEvent = new Map<string, { rank: number; peakValue: number }>();

    for (const row of rows) {
      if (!row.event_above_id) continue;
      const rank = toNumber(row.event_above_peak_rank);
      if (rank === null) continue;

      const peakValue = toNumber(row.peak_value) ?? Number.NEGATIVE_INFINITY;
      const existing = byEvent.get(row.event_above_id);

      if (!existing) {
        byEvent.set(row.event_above_id, { rank, peakValue });
        continue;
      }

      if (rank < existing.rank || (rank === existing.rank && peakValue > existing.peakValue)) {
        byEvent.set(row.event_above_id, { rank, peakValue });
      }
    }

    return [...byEvent.entries()]
      .map(([eventId, detail]) => ({
        eventId,
        rank: detail.rank,
        peakValue: detail.peakValue,
        label: intervalStartDate(eventId),
      }))
      .sort((a, b) => {
        if (a.rank !== b.rank) return a.rank - b.rank;
        if (a.peakValue !== b.peakValue) return b.peakValue - a.peakValue;
        return a.eventId.localeCompare(b.eventId);
      });
  }, [rankingsQuery.data]);

  const topEvents = useMemo(() => rankedEvents.slice(0, topN), [rankedEvents, topN]);

  const isLoading = rankingsQuery.isLoading || heatmapQuery.isLoading || thresholdValues.isLoading;
  const isError = rankingsQuery.isError || heatmapQuery.isError || thresholdValues.isError;
  const error = rankingsQuery.error ?? heatmapQuery.error ?? thresholdValues.error;

  if (!selectedLocation) {
    return (
      <div className="firo-empty-state d-flex align-items-center justify-content-center h-100 text-muted m-3">
        <p className="mb-0">No location selected. Return to Location Selection to choose one.</p>
      </div>
    );
  }

  return (
    <div className="firo-page">
      <div className="firo-page-header">
        <h6 className="firo-page-title fw-semibold">Top Events Performance Analysis</h6>
        <p className="firo-page-subtitle small mb-0">{selectedLocation.name}</p>
      </div>

      <Card className="firo-filter-card">
        <Card.Body>
          <div className="firo-top-events-filters">
            <Form.Group controlId="firo-top-events-threshold">
              <Form.Label className="firo-filter-label mb-1">Observed Flow Quantile</Form.Label>
              <Form.Select
                size="sm"
                className="firo-select"
                value={selectedThresholdValue}
                onChange={(e) => setThreshold(e.target.value)}
                style={{ minWidth: '190px' }}
              >
                {hasAllThresholdOption && <option value={ALL_THRESHOLDS}>All Quantiles</option>}
                {thresholdOptions.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>

            <Form.Group controlId="firo-top-events-count">
              <Form.Label className="firo-filter-label mb-1">Number of Top Events</Form.Label>
              <Form.Select
                size="sm"
                className="firo-select"
                value={String(topN)}
                onChange={(e) => setTopN(Number(e.target.value))}
                style={{ minWidth: '160px' }}
              >
                {Array.from({ length: 20 }, (_, i) => i + 1).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </div>
        </Card.Body>
      </Card>

      <Card className="firo-metric-card">
        <Card.Header className="firo-metric-card-header">
          <div className="firo-heatmap-head-row">
            <div>
              <span className="firo-metric-card-title small fw-semibold">
                Event vs Lead Time Heatmap
              </span>
              <p className="firo-page-subtitle small mb-0">
                X: Event Date | Y: Lead Time | Color: Metric Value
              </p>
            </div>

            <div className="btn-group" aria-label="Heatmap metric selector">
              {METRIC_OPTIONS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className={`btn btn-sm ${metricKey === option.key ? 'btn-primary' : 'btn-outline-primary'}`}
                  onClick={() => setMetricKey(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </Card.Header>

        <Card.Body className="firo-metric-card-body">
          {isLoading && (
            <div className="d-flex align-items-center justify-content-center h-100 text-muted">
              <Spinner animation="border" size="sm" className="me-2" />
              <span className="small">Loading top event heatmap…</span>
            </div>
          )}

          {isError && (
            <Alert variant="danger" className="mb-0">
              Failed to load top event data:{' '}
              {error instanceof Error ? error.message : 'Unknown error'}
            </Alert>
          )}

          {!isLoading && !isError && !topEvents.length && (
            <div className="firo-empty-state d-flex align-items-center justify-content-center h-100 text-muted">
              <p className="mb-0 small">No ranked events found for the current filter selection.</p>
            </div>
          )}

          {!isLoading && !isError && topEvents.length > 0 && (
            <div className="firo-heatmap-expandable">
              <TopEventsHeatmap
                data={heatmapQuery.data ?? []}
                topEvents={topEvents}
                metricKey={metricKey}
                metricLabel={
                  METRIC_OPTIONS.find((option) => option.key === metricKey)?.label ?? 'Metric'
                }
                maxRows={heatmapExpanded ? undefined : 4}
              />
              <button
                type="button"
                className="firo-heatmap-expand-btn"
                onClick={() => setHeatmapExpanded((prev) => !prev)}
                aria-expanded={heatmapExpanded}
                aria-label={heatmapExpanded ? 'Collapse heatmap' : 'Expand heatmap'}
              >
                {heatmapExpanded ? '▲ Show Less' : '▼ Show All Rows'}
              </button>
            </div>
          )}
        </Card.Body>
      </Card>
    </div>
  );
};
