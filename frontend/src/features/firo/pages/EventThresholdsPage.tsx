import { useMemo, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Col from 'react-bootstrap/Col';
import Row from 'react-bootstrap/Row';
import Spinner from 'react-bootstrap/Spinner';

import LeadTimeMetricChart from '../components/LeadTimeMetricChart';
import {
  LeadTimeGranularityToggle,
  type LeadTimeGranularity,
} from '../components/LeadTimeGranularityToggle';
import { NULL_VALUE, SeasonQuantileFilters } from '../components/SeasonQuantileFilters';
import { useLeadTimeMetrics } from '../hooks/useLeadTimeMetrics';
import { aggregateLeadTimeMetricsByDay } from '../utils/aggregateLeadTimeMetricsByDay';
import { useFiroDashboardStore } from '../store';

export const EventThresholdsPage = () => {
  const selectedLocation = useFiroDashboardStore((s) => s.selectedLocation);

  const [season, setSeason] = useState<string>(NULL_VALUE);
  const [threshold, setThreshold] = useState<string>(NULL_VALUE);
  const [granularity, setGranularity] = useState<LeadTimeGranularity>('daily');

  const { data: rawData, isLoading, isError, error } = useLeadTimeMetrics({
    primaryLocationId: selectedLocation?.primary_location_id ?? null,
    season: season || null,
    threshold: threshold || null,
  });

  const data = useMemo(
    () =>
      rawData && granularity === 'daily'
        ? aggregateLeadTimeMetricsByDay(rawData)
        : rawData,
    [rawData, granularity],
  );

  if (!selectedLocation) {
    return (
      <div className="firo-empty-state d-flex align-items-center justify-content-center h-100 text-muted m-3">
        <p className="mb-0">No location selected. Return to Location Selection to choose one.</p>
      </div>
    );
  }

  return (
    <div className="firo-page">
      {/* Page header */}
      <div className="firo-page-header">
        <h6 className="firo-page-title fw-semibold">Event Threshold Metrics</h6>
        <p className="firo-page-subtitle small">{selectedLocation.name}</p>
      </div>

      {/* Filters */}
      <SeasonQuantileFilters
        season={season}
        setSeason={setSeason}
        threshold={threshold}
        setThreshold={setThreshold}
      >
        <LeadTimeGranularityToggle value={granularity} onChange={setGranularity} />
      </SeasonQuantileFilters>

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
        <div className="firo-empty-state d-flex align-items-center justify-content-center flex-grow-1 text-muted">
          <p className="mb-0 small">No data available for the selected filters.</p>
        </div>
      )}

      {!isLoading && !isError && data && data.length > 0 && (
        <Row className="firo-metric-grid g-3">
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
              <Card className="firo-metric-card">
                <Card.Header className="firo-metric-card-header">
                  <span className="firo-metric-card-title small fw-semibold">
                    {label} vs. Lead Time
                  </span>
                </Card.Header>
                <Card.Body className="firo-metric-card-body">
                  <LeadTimeMetricChart
                    data={data}
                    metricKey={key}
                    yAxisLabel={yAxisLabel}
                    yRangeMode={yRangeMode}
                    granularity={granularity}
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
