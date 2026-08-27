import { useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';
import Spinner from 'react-bootstrap/Spinner';

import { useLeadTimeMetrics } from '../hooks/useLeadTimeMetrics';
import { useFiroDashboardStore } from '../store';
import LeadTimeMetricChart from './LeadTimeMetricChart';
import { NULL_VALUE, SeasonQuantileFilters } from './SeasonQuantileFilters';

export const EventThresholdsPage = () => {
  const selectedLocation = useFiroDashboardStore((s) => s.selectedLocation);

  const [season, setSeason] = useState<string>(NULL_VALUE);
  const [threshold, setThreshold] = useState<string>(NULL_VALUE);

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
        <h6 className="fw-semibold mb-0">Event Thresholds</h6>
        <p className="text-muted small mb-0">{selectedLocation.name}</p>
      </div>

      {/* Filters */}
      <SeasonQuantileFilters
        season={season}
        setSeason={setSeason}
        threshold={threshold}
        setThreshold={setThreshold}
      />

      {/* 2-chart grid */}
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
                key: 'mean_brier_score',
                label: 'BS',
                yAxisLabel: 'Brier Score (BS)',
                yRangeMode: 'tozero',
              },
              {
                key: 'mean_brier_score_skill_score',
                label: 'BSS',
                yAxisLabel: 'Brier Skill Score (BSS)',
                yRangeMode: 'normal',
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
