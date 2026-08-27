import { useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Form from 'react-bootstrap/Form';
import Row from 'react-bootstrap/Row';
import Spinner from 'react-bootstrap/Spinner';

import { useDistinctValues } from '@/shared/queries/distinctValues';

import { useLeadTimeMetrics } from '../hooks/useLeadTimeMetrics';
import { useFiroDashboardStore } from '../store';
import LeadTimeMetricChart from './LeadTimeMetricChart';

const TABLE = 'locations_metrics';
const NULL_VALUE = 'null'; // sent to the API to match pre-computed "null" rows

/**
 * Convert a raw quantile key (e.g. "q_10th") to a readable label ("10th Percentile").
 * Falls back to the raw value for unrecognised strings.
 */
const formatQuantileLabel = (value: string): string => {
  const match = value.match(/^q_(\d+)th$/i);
  if (match) return `${match[1]}th Percentile`;
  return value;
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export const DeterministicPage = () => {
  const selectedLocation = useFiroDashboardStore((s) => s.selectedLocation);

  const [season, setSeason] = useState<string>(NULL_VALUE);
  const [threshold, setThreshold] = useState<string>(NULL_VALUE);

  const seasons = useDistinctValues(TABLE, 'season');
  const thresholds = useDistinctValues(TABLE, 'threshold');

  const { data, isLoading, isError, error } = useLeadTimeMetrics({
    primaryLocationId: selectedLocation?.primary_location_id ?? null,
    season: season || null,
    threshold: threshold || null,
  });

  if (!selectedLocation) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted">
        <p className="mb-0">No location selected. Return to Location Selection to choose one.</p>
      </div>
    );
  }

  return (
    <div className="d-flex flex-column h-100 overflow-auto p-3">
      {/* Page header */}
      <div className="mb-3">
        <h6 className="fw-semibold mb-0">Deterministic</h6>
        <p className="text-muted small mb-0">{selectedLocation.name}</p>
      </div>

      {/* Filters */}
      <Card className="mb-3 border-0 shadow-sm">
        <Card.Body className="py-2 px-3">
          <Row className="g-3 align-items-end">
            <Col xs="auto">
              <Form.Group controlId="firo-season">
                <Form.Label className="small fw-semibold mb-1">Season</Form.Label>
                <Form.Select
                  size="sm"
                  value={season}
                  onChange={(e) => setSeason(e.target.value)}
                  style={{ minWidth: '160px' }}
                  disabled={seasons.isLoading}
                >
                  <option value={NULL_VALUE}>All Seasons</option>
                  {seasons.data
                    ?.filter((s) => s !== null && s !== 'null' && s !== 'None')
                    .map((s) => (
                      <option key={s} value={s}>
                        {s.charAt(0).toUpperCase() + s.slice(1)}
                      </option>
                    ))}
                </Form.Select>
              </Form.Group>
            </Col>

            <Col xs="auto">
              <Form.Group controlId="firo-quantile">
                <Form.Label className="small fw-semibold mb-1">Observed Flow Quantile</Form.Label>
                <Form.Select
                  size="sm"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  style={{ minWidth: '220px' }}
                  disabled={thresholds.isLoading}
                >
                  <option value={NULL_VALUE}>All Quantiles</option>
                  {thresholds.data
                    ?.filter((t) => t !== null && t !== 'null' && t !== 'None')
                    .map((t) => (
                      <option key={t} value={t}>
                        {formatQuantileLabel(t)}
                      </option>
                    ))}
                </Form.Select>
              </Form.Group>
            </Col>
          </Row>
        </Card.Body>
      </Card>

      {/* 2×2 chart grid */}
      {isLoading && (
        <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
          <Spinner animation="border" size="sm" className="me-2" />
          <span className="small">Loading metrics…</span>
        </div>
      )}

      {isError && (
        <Alert variant="danger">
          Failed to load metrics: {error instanceof Error ? error.message : 'Unknown error'}
        </Alert>
      )}

      {!isLoading && !isError && data?.length === 0 && (
        <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
          <p className="mb-0 small">No data available for the selected filters.</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <Row className="g-3">
          {(
            [
              {
                key: 'mean_absolute_error',
                label: 'MAE',
                yAxisLabel: 'Mean Absolute Error (MAE)',
                yRangeMode: 'tozero',
              },
              {
                key: 'root_mean_square_error',
                label: 'RMSE',
                yAxisLabel: 'Root Mean Square Error (RMSE)',
                yRangeMode: 'tozero',
              },
              {
                key: 'relative_bias',
                label: 'Relative Bias',
                yAxisLabel: 'Relative Bias',
                yRangeMode: 'normal',
              },
              {
                key: 'pearson_correlation',
                label: 'Correlation',
                yAxisLabel: 'Pearson Correlation',
                yRangeMode: 'normal',
              },
              {
                key: 'probability_of_detection',
                label: 'POD',
                yAxisLabel: 'Probability of Detection (POD)',
                yRangeMode: 'tozero',
              },
              {
                key: 'false_alarm_ratio',
                label: 'FAR',
                yAxisLabel: 'False Alarm Ratio (FAR)',
                yRangeMode: 'tozero',
              },
              {
                key: 'critical_success_index',
                label: 'CSI',
                yAxisLabel: 'Critical Success Index (CSI)',
                yRangeMode: 'tozero',
              },
              {
                key: 'frequency_bias_index',
                label: 'Frequency Bias',
                yAxisLabel: 'Frequency Bias Index',
                yRangeMode: 'tozero',
              },
            ] as const
          ).map(({ key, label, yAxisLabel, yRangeMode }) => (
            <Col key={key} xs={12} md={6}>
              <Card className="border-0 shadow-sm">
                <Card.Header className="bg-white border-bottom py-2 px-3">
                  <span className="small fw-semibold">{label} vs. Lead Time</span>
                </Card.Header>
                <Card.Body className="p-2">
                  <LeadTimeMetricChart
                    data={data}
                    metricKey={key}
                    yAxisLabel={yAxisLabel}
                    yRangeMode={yRangeMode}
                  />
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
};
