import { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Form } from 'react-bootstrap';
import Plotly from 'plotly.js-dist-min';

const EnsemblePerformance = ({ selectedLocation, joinedTimeseries = [], loading = false, error = null }) => {
  const plotRef = useRef(null);
  const [selectedLeadTime, setSelectedLeadTime] = useState('');

  const availableLeadTimes = useMemo(() => {
    const values = joinedTimeseries.map((row) => row.reference_time).filter(Boolean);
    return [...new Set(values)].sort();
  }, [joinedTimeseries]);

  useEffect(() => {
    if (!selectedLeadTime && availableLeadTimes.length > 0) setSelectedLeadTime(availableLeadTimes[0]);
  }, [availableLeadTimes, selectedLeadTime]);

  useEffect(() => {
    if (!plotRef.current) return;
    const filtered = joinedTimeseries.filter((row) => row.reference_time === selectedLeadTime);
    if (!filtered.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    const observations = filtered.map((row) => row.primary_value);
    const simulations = filtered.map((row) => row.secondary_value);

    Plotly.react(plotRef.current, [{
      y: observations,
      x: simulations,
      type: 'box',
      boxpoints: false,
      name: 'Simulated vs observed',
      marker: { color: '#0d6efd' },
    }], {
      title: { text: 'Ensemble performance by observed value' },
      xaxis: { title: { text: 'Simulated values' } },
      yaxis: { title: { text: 'Observed values' } },
      margin: { l: 80, r: 20, t: 50, b: 60 },
    }, { responsive: true, displayModeBar: 'hover' });
  }, [joinedTimeseries, selectedLeadTime]);

  if (!selectedLocation) return null;

  return (
    <Card className="shadow-sm" style={{ borderRadius: '8px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Card.Header className="py-2">
        <strong>Ensemble Performance</strong>
      </Card.Header>
      <Card.Body className="d-flex flex-column" style={{ gap: '10px', flex: '1 1 0', minHeight: 0 }}>
        {loading ? (
          <div className="text-muted small">Loading ensemble performance...</div>
        ) : error ? (
          <div className="text-danger small">{error}</div>
        ) : (
          <>
            <Form.Label className="small fw-bold">Lead Time</Form.Label>
            <Form.Select value={selectedLeadTime} onChange={(e) => setSelectedLeadTime(e.target.value)}>
              <option value="">Select lead time...</option>
              {availableLeadTimes.map((leadTime) => (
                <option key={leadTime} value={leadTime}>{leadTime}</option>
              ))}
            </Form.Select>
            <div ref={plotRef} style={{ width: '100%', flex: '1 1 0', minHeight: '200px' }} />
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default EnsemblePerformance;
