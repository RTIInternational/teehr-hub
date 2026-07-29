import { useEffect, useMemo, useRef, useState } from 'react';
import { Card, Form, Spinner } from 'react-bootstrap';
import Plotly from 'plotly.js-dist-min';

const EventViewer = ({
  selectedLocation,
  mapFilters,
  eventRankings = [],
  joinedTimeseries = [],
  loading = false,
  error = null,
}) => {
  const plotRef = useRef(null);
  const [selectedEvent, setSelectedEvent] = useState('');
  const [selectedLeadTime, setSelectedLeadTime] = useState('');

  const availableEvents = useMemo(() => {
    const events = eventRankings
      .map((row) => row.event_above_id)
      .filter((value) => value !== null && value !== undefined && value !== '');
    return [...new Set(events)];
  }, [eventRankings]);

  const availableLeadTimes = useMemo(() => {
    const values = joinedTimeseries
      .map((row) => row.reference_time)
      .filter((value) => value !== null && value !== undefined && value !== '');
    return [...new Set(values)].sort();
  }, [joinedTimeseries]);

  useEffect(() => {
    if (!selectedEvent && availableEvents.length > 0) {
      setSelectedEvent(availableEvents[0]);
    }
  }, [availableEvents, selectedEvent]);

  useEffect(() => {
    if (!selectedLeadTime && availableLeadTimes.length > 0) {
      setSelectedLeadTime(availableLeadTimes[0]);
    }
  }, [availableLeadTimes, selectedLeadTime]);

  const selectedEventRow = useMemo(() => {
    if (!selectedEvent) return null;
    return eventRankings.find((row) => row.event_above_id === selectedEvent) || null;
  }, [eventRankings, selectedEvent]);

  const plotRows = useMemo(() => {
    if (!selectedLeadTime) return [];
    return joinedTimeseries.filter((row) => row.reference_time === selectedLeadTime);
  }, [joinedTimeseries, selectedLeadTime]);

  useEffect(() => {
    if (!plotRef.current) return;

    if (!plotRows.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    const observedSeries = plotRows.map((row) => ({
      x: row.value_time,
      y: row.primary_value,
    }));

    const groupedSecondary = {};
    plotRows.forEach((row) => {
      const key = row.member || 'ensemble';
      if (!groupedSecondary[key]) groupedSecondary[key] = [];
      groupedSecondary[key].push(row.secondary_value);
    });

    const series = Object.entries(groupedSecondary).map(([member, values]) => ({
      y: values,
      x: observedSeries.map((row) => row.x),
      type: 'scatter',
      mode: 'lines',
      name: member === 'ensemble' ? 'Ensemble mean' : `Member ${member}`,
      line: { width: 1.5 },
    }));

    const tracedObserved = {
      x: observedSeries.map((row) => row.x),
      y: observedSeries.map((row) => row.y),
      type: 'scatter',
      mode: 'lines',
      name: 'Observed',
      line: { color: '#1f77b4', width: 2.5 },
    };

    Plotly.react(plotRef.current, [tracedObserved, ...series], {
      title: { text: `Event view for ${selectedEvent || 'selected event'}` },
      xaxis: { title: { text: 'Value time' } },
      yaxis: { title: { text: 'Value' } },
      margin: { l: 60, r: 20, t: 50, b: 50 },
      showlegend: true,
      legend: { x: 1.01, y: 1 },
    }, { responsive: true, displayModeBar: 'hover' });
  }, [plotRows, selectedEvent]);

  if (!selectedLocation) return null;

  return (
    <Card className="shadow-sm h-100" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2">
        <strong>Event Viewer</strong>
      </Card.Header>
      <Card.Body className="d-flex flex-column" style={{ gap: '10px' }}>
        {loading ? (
          <div className="d-flex flex-grow-1 align-items-center justify-content-center text-muted">
            <Spinner animation="border" size="sm" />
            <span className="ms-2">Loading event data...</span>
          </div>
        ) : error ? (
          <div className="text-danger small">{error}</div>
        ) : (
          <>
            <div className="row g-2">
              <div className="col-md-6">
                <Form.Label className="small fw-bold">Event</Form.Label>
                <Form.Select value={selectedEvent} onChange={(e) => setSelectedEvent(e.target.value)}>
                  <option value="">Select event...</option>
                  {availableEvents.map((eventId) => (
                    <option key={eventId} value={eventId}>{eventId}</option>
                  ))}
                </Form.Select>
              </div>
              <div className="col-md-6">
                <Form.Label className="small fw-bold">Lead Time</Form.Label>
                <Form.Select value={selectedLeadTime} onChange={(e) => setSelectedLeadTime(e.target.value)}>
                  <option value="">Select lead time...</option>
                  {availableLeadTimes.map((leadTime) => (
                    <option key={leadTime} value={leadTime}>{leadTime}</option>
                  ))}
                </Form.Select>
              </div>
            </div>

            {selectedEventRow ? (
              <div className="small text-muted">
                Event peak rank: {selectedEventRow.event_above_peak_rank ?? 'N/A'} • Peak value: {selectedEventRow.peak_value ?? 'N/A'} • Threshold: {selectedEventRow.threshold ?? 'N/A'}
              </div>
            ) : (
              <div className="small text-muted">Select an event to view supporting details.</div>
            )}

            <div ref={plotRef} style={{ width: '100%', height: '280px' }} />
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default EventViewer;
