import { useMemo, useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Spinner from 'react-bootstrap/Spinner';

import {
  useEventTraceInitializations,
  useEventTraceData,
} from '../hooks/useEventTraceInitializations';
import { EventTraceObservedPlot } from './EventTraceObservedPlot';
import type { TopEventSummary } from './TopEventsHeatmap';

const ALL_THRESHOLDS = 'all';
const LEAD_TIME_OPTIONS = [24, 48, 72] as const;

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
  const [leadTimeHours, setLeadTimeHours] = useState<number>(48);
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
    leadTimeHours,
  });

  const effectiveSelectedInitializationDatetime = useMemo(() => {
    const initializationOptions =
      initializationQuery.data?.available_initialization_datetimes ?? [];
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
  }, [initializationQuery.data, selectedInitializationDatetime]);

  const traceDataQuery = useEventTraceData({
    primaryLocationId,
    configurationName,
    variableName,
    threshold: traceThreshold,
    windowStart: initializationQuery.data?.expanded_event_start ?? null,
    windowEnd: initializationQuery.data?.expanded_event_end ?? null,
    initializationTime: effectiveSelectedInitializationDatetime,
  });

  const selectedInitializationIndex = useMemo(() => {
    const initializationOptions =
      initializationQuery.data?.available_initialization_datetimes ?? [];
    return effectiveSelectedInitializationDatetime
      ? Math.max(initializationOptions.indexOf(effectiveSelectedInitializationDatetime), 0)
      : 0;
  }, [effectiveSelectedInitializationDatetime, initializationQuery.data]);

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

          <Form.Group controlId="firo-trace-lead-time-select">
            <Form.Label className="firo-filter-label mb-1">Lead Time</Form.Label>
            <Form.Select
              size="sm"
              className="firo-select"
              value={String(leadTimeHours)}
              onChange={(e) => {
                setLeadTimeHours(Number(e.target.value));
                setSelectedInitializationDatetime('');
              }}
              style={{ minWidth: '160px' }}
            >
              {LEAD_TIME_OPTIONS.map((hours) => (
                <option key={hours} value={String(hours)}>
                  {hours} hours
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
                  max={Math.max(
                    (initializationQuery.data?.available_initialization_datetimes ?? []).length - 1,
                    0
                  )}
                  step={1}
                  value={selectedInitializationIndex}
                  onChange={(e) => {
                    const nextIndex = Number(e.target.value);
                    const initializationOptions =
                      initializationQuery.data?.available_initialization_datetimes ?? [];
                    setSelectedInitializationDatetime(initializationOptions[nextIndex] ?? '');
                  }}
                  disabled={
                    (initializationQuery.data?.available_initialization_datetimes ?? []).length ===
                    0
                  }
                />
                <div className="firo-trace-slider-readout">
                  <span>
                    Expanded Start: {initializationQuery.data?.expanded_event_start ?? 'N/A'}
                  </span>
                  <span>Selected: {effectiveSelectedInitializationDatetime ?? 'N/A'}</span>
                  <span>Expanded End: {initializationQuery.data?.expanded_event_end ?? 'N/A'}</span>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="firo-trace-plot-container mt-3">
          {traceDataQuery.isLoading && (
            <div className="d-flex align-items-center justify-content-center text-muted small p-5">
              <Spinner animation="border" size="sm" className="me-2" />
              Loading trace data...
            </div>
          )}

          {traceDataQuery.isError && (
            <Alert variant="danger" className="mb-2 py-2 small">
              Failed to load trace data:{' '}
              {traceDataQuery.error instanceof Error
                ? traceDataQuery.error.message
                : 'Unknown error'}
            </Alert>
          )}

          {traceDataQuery.isSuccess && traceDataQuery.data && (
            <EventTraceObservedPlot data={traceDataQuery.data} />
          )}

          {!traceThreshold && (
            <div className="text-center text-muted small p-5">
              <p className="mb-0">Select a specific quantile to load trace data.</p>
            </div>
          )}
        </div>
      </Card.Body>
    </>
  );
};
