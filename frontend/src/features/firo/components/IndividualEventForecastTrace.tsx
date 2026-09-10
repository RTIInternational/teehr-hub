import { useMemo, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Spinner from 'react-bootstrap/Spinner';

import { useEventTraceInitializations } from '../hooks/useEventTraceInitializations';
import type { TopEventSummary } from './TopEventsHeatmap';

const ALL_THRESHOLDS = 'all';

type IndividualEventForecastTraceProps = {
  rankedEvents: TopEventSummary[];
  effectiveThreshold: string | null;
  primaryLocationId: string;
  configurationName: string;
  variableName: string;
};

export const IndividualEventForecastTrace = ({
  rankedEvents,
  effectiveThreshold,
  primaryLocationId,
  configurationName,
  variableName,
}: IndividualEventForecastTraceProps) => {
  const [selectedEventId, setSelectedEventId] = useState<string>('');
  const [selectedInitializationDatetime, setSelectedInitializationDatetime] = useState<string>('');

  const effectiveSelectedEventId =
    selectedEventId && rankedEvents.some((event) => event.eventId === selectedEventId)
      ? selectedEventId
      : (rankedEvents[0]?.eventId ?? '');

  const traceThreshold =
    effectiveThreshold && effectiveThreshold !== ALL_THRESHOLDS ? effectiveThreshold : null;

  const initializationQuery = useEventTraceInitializations({
    primaryLocationId,
    configurationName,
    variableName,
    threshold: traceThreshold,
    eventId: effectiveSelectedEventId || null,
  });

  const initializationOptions = useMemo(
    () => initializationQuery.data?.available_initialization_datetimes ?? [],
    [initializationQuery.data]
  );

  const effectiveSelectedInitializationDatetime = useMemo(() => {
    if (!initializationOptions.length) return null;
    if (
      selectedInitializationDatetime &&
      initializationOptions.includes(selectedInitializationDatetime)
    ) {
      return selectedInitializationDatetime;
    }

    const defaultDatetime = initializationQuery.data?.default_initialization_datetime;
    if (defaultDatetime && initializationOptions.includes(defaultDatetime)) {
      return defaultDatetime;
    }

    return initializationOptions[0];
  }, [initializationOptions, initializationQuery.data, selectedInitializationDatetime]);

  const selectedInitializationIndex = effectiveSelectedInitializationDatetime
    ? Math.max(initializationOptions.indexOf(effectiveSelectedInitializationDatetime), 0)
    : 0;

  return (
    <>
      <Card.Header className="firo-metric-card-header">
        <div>
          <span className="firo-metric-card-title small fw-semibold">
            Individual Event Forecast Trace
          </span>
          <p className="firo-page-subtitle small mb-0">
            Select an event and initialization datetime to prepare trace plotting.
          </p>
        </div>
      </Card.Header>

      <Card.Body className="firo-metric-card-body">
        <div className="firo-trace-controls">
          <Form.Group controlId="firo-trace-event-select">
            <Form.Label className="firo-filter-label mb-1">Event</Form.Label>
            <Form.Select
              size="sm"
              className="firo-select"
              value={effectiveSelectedEventId}
              onChange={(e) => {
                setSelectedEventId(e.target.value);
                setSelectedInitializationDatetime('');
              }}
              disabled={!rankedEvents.length}
              style={{ minWidth: '280px' }}
            >
              {!rankedEvents.length && <option value="">No events available</option>}
              {rankedEvents.map((event) => (
                <option key={event.eventId} value={event.eventId}>
                  #{event.rank} - {event.label}
                </option>
              ))}
            </Form.Select>
          </Form.Group>

          <div className="firo-trace-slider-group">
            <Form.Label className="firo-filter-label mb-1">Initialization Datetime</Form.Label>

            {!traceThreshold && (
              <p className="small text-muted mb-2">
                Select a specific quantile to load initialization options.
              </p>
            )}

            {traceThreshold && initializationQuery.isLoading && (
              <div className="d-flex align-items-center text-muted small mb-2">
                <Spinner animation="border" size="sm" className="me-2" />
                Loading initialization datetimes...
              </div>
            )}

            {traceThreshold && initializationQuery.isError && (
              <Alert variant="danger" className="mb-2 py-2 small">
                Failed to load initialization options:{' '}
                {initializationQuery.error instanceof Error
                  ? initializationQuery.error.message
                  : 'Unknown error'}
              </Alert>
            )}

            {traceThreshold && !initializationQuery.isLoading && !initializationQuery.isError && (
              <>
                <Form.Range
                  min={0}
                  max={Math.max(initializationOptions.length - 1, 0)}
                  step={1}
                  value={selectedInitializationIndex}
                  onChange={(e) => {
                    const nextIndex = Number(e.target.value);
                    setSelectedInitializationDatetime(initializationOptions[nextIndex] ?? '');
                  }}
                  disabled={initializationOptions.length === 0}
                />
                <div className="firo-trace-slider-readout">
                  <span>Start: {initializationOptions[0] ?? 'N/A'}</span>
                  <span>Selected: {effectiveSelectedInitializationDatetime ?? 'N/A'}</span>
                  <span>
                    End: {initializationOptions[initializationOptions.length - 1] ?? 'N/A'}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="firo-trace-placeholder mt-3">
          <p className="mb-0 small text-muted">
            Event trace plot scaffolding is ready. The chart will appear here once the trace
            endpoint is wired.
          </p>
        </div>
      </Card.Body>
    </>
  );
};
