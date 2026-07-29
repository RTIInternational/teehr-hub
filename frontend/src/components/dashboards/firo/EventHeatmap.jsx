import { useMemo, useState } from 'react';
import { Card, Form } from 'react-bootstrap';
import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

const EventHeatmap = ({ selectedLocation, eventHeatmap = [], loading = false, error = null }) => {
  const plotRef = useRef(null);
  const [selectedThreshold, setSelectedThreshold] = useState('');
  const [selectedMetric, setSelectedMetric] = useState('relative_bias');

  const availableThresholds = useMemo(() => {
    const values = eventHeatmap.map((row) => row.threshold).filter((value) => value !== null && value !== undefined && value !== '');
    return [...new Set(values)];
  }, [eventHeatmap]);

  const availableMetrics = useMemo(() => {
    const metrics = eventHeatmap.filter((row) => row[selectedMetric] !== undefined);
    return metrics.length > 0 ? ['relative_bias', 'root_mean_square_error', 'pearson_correlation'] : [];
  }, [eventHeatmap, selectedMetric]);

  useEffect(() => {
    if (!selectedThreshold && availableThresholds.length > 0) setSelectedThreshold(availableThresholds[0]);
  }, [availableThresholds, selectedThreshold]);

  useEffect(() => {
    if (!plotRef.current) return;
    const filtered = eventHeatmap.filter((row) => row.threshold === selectedThreshold);
    if (!filtered.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    const xValues = filtered.map((row) => row.event_id);
    const yValues = filtered.map((row) => row.forecast_lead_time_bin);
    const zValues = filtered.map((row) => Number(row[selectedMetric]));

    Plotly.react(plotRef.current, [{
      x: xValues,
      y: yValues,
      z: [zValues],
      type: 'heatmap',
      colorscale: 'Viridis',
      colorbar: { title: selectedMetric },
    }], {
      title: { text: `Heatmap for ${selectedMetric}` },
      xaxis: { title: { text: 'Event' } },
      yaxis: { title: { text: 'Lead Time Bin' } },
      margin: { l: 80, r: 20, t: 50, b: 80 },
    }, { responsive: true, displayModeBar: 'hover' });
  }, [eventHeatmap, selectedMetric, selectedThreshold]);

  if (!selectedLocation) return null;

  return (
    <Card className="shadow-sm h-100" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2">
        <strong>Event Heatmap</strong>
      </Card.Header>
      <Card.Body className="d-flex flex-column" style={{ gap: '10px' }}>
        {loading ? (
          <div className="text-muted small">Loading heatmap...</div>
        ) : error ? (
          <div className="text-danger small">{error}</div>
        ) : (
          <>
            <div className="row g-2">
              <div className="col-md-6">
                <Form.Label className="small fw-bold">Threshold</Form.Label>
                <Form.Select value={selectedThreshold} onChange={(e) => setSelectedThreshold(e.target.value)}>
                  <option value="">Select threshold...</option>
                  {availableThresholds.map((threshold) => (
                    <option key={threshold} value={threshold}>{threshold}</option>
                  ))}
                </Form.Select>
              </div>
              <div className="col-md-6">
                <Form.Label className="small fw-bold">Metric</Form.Label>
                <Form.Select value={selectedMetric} onChange={(e) => setSelectedMetric(e.target.value)}>
                  {availableMetrics.map((metric) => (
                    <option key={metric} value={metric}>{metric}</option>
                  ))}
                </Form.Select>
              </div>
            </div>
            <div ref={plotRef} style={{ width: '100%', height: '280px' }} />
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default EventHeatmap;
