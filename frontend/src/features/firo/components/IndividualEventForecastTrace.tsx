import { useState } from 'react';
import Alert from 'react-bootstrap/Alert';
import Card from 'react-bootstrap/Card';
import Form from 'react-bootstrap/Form';
import Spinner from 'react-bootstrap/Spinner';

import {
  useEventTraceInitializations,
  useEventTraceData,
} from '../hooks/useEventTraceInitializations';
import { EventTracePlot } from './EventTracePlot';
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
  const [selectedInitializationIndex, setSelectedInitializationIndex] = useState<number | null>(
    null
  );
  const [committedInitializationDatetime, setCommittedInitializationDatetime] = useState<
    string | null
  >(null);

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

  const initializationOptions = initializationQuery.data?.available_initialization_datetimes ?? [];

  const defaultInitializationDatetime =
    (initializationQuery.data?.default_initialization_datetime ?? initializationOptions[0]) || null;
  const defaultInitializationIndex = defaultInitializationDatetime
    ? Math.max(initializationOptions.indexOf(defaultInitializationDatetime), 0)
    : 0;
  const effectiveSelectedInitializationIndex =
    selectedInitializationIndex !== null &&
    selectedInitializationIndex >= 0 &&
    selectedInitializationIndex < initializationOptions.length
      ? selectedInitializationIndex
      : defaultInitializationIndex;
  const effectiveSelectedInitializationDatetime =
    initializationOptions[effectiveSelectedInitializationIndex] ?? null;
  const committedInitializationForQuery =
    committedInitializationDatetime &&
    initializationOptions.includes(committedInitializationDatetime)
      ? committedInitializationDatetime
      : defaultInitializationDatetime;

  const traceDataQuery = useEventTraceData({
    primaryLocationId,
    configurationName,
    variableName,
    threshold: traceThreshold,
    windowStart: initializationQuery.data?.expanded_event_start ?? null,
    windowEnd: initializationQuery.data?.expanded_event_end ?? null,
    initializationTime: committedInitializationForQuery,
  });

  const isShowingPreviousTraceWhileUpdating =
    !!committedInitializationForQuery &&
    !!traceDataQuery.data?.initialization_datetime &&
    traceDataQuery.data.initialization_datetime !== committedInitializationForQuery;

  const commitInitializationSelection = (index: number) => {
    const nextDatetime = initializationOptions[index] ?? null;
    setCommittedInitializationDatetime(nextDatetime);
  };

  const sliderTickCount = initializationOptions.length;

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
                setSelectedInitializationIndex(null);
                setCommittedInitializationDatetime(null);
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
                setSelectedInitializationIndex(null);
                setCommittedInitializationDatetime(null);
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
            <Form.Label className="firo-filter-label mb-1">
              {initializationQuery.isLoading ? (
                <span className="d-inline-flex align-items-center">
                  <Spinner animation="border" size="sm" className="me-2" />
                  Loading initialization datetimes...
                </span>
              ) : (
                <span>
                  Initialization Datetime: {effectiveSelectedInitializationDatetime ?? 'N/A'}
                </span>
              )}
            </Form.Label>

            {!traceThreshold && (
              <p className="small text-muted mb-2">
                Select a specific quantile to load initialization options.
              </p>
            )}

            {traceThreshold && initializationQuery.isError && (
              <Alert variant="danger" className="mb-2 py-2 small">
                Failed to load initialization options:{' '}
                {initializationQuery.error instanceof Error
                  ? initializationQuery.error.message
                  : 'Unknown error'}
              </Alert>
            )}

            {traceThreshold && !initializationQuery.isError && (
              <div className="firo-trace-slider-shell">
                <Form.Range
                  min={0}
                  max={Math.max(
                    (initializationQuery.data?.available_initialization_datetimes ?? []).length - 1,
                    0
                  )}
                  step={1}
                  value={effectiveSelectedInitializationIndex}
                  onChange={(e) => {
                    const nextIndex = Number(e.target.value);
                    setSelectedInitializationIndex(nextIndex);
                  }}
                  onMouseUp={(e) => commitInitializationSelection(Number(e.currentTarget.value))}
                  onTouchEnd={(e) => commitInitializationSelection(Number(e.currentTarget.value))}
                  onKeyUp={(e) => commitInitializationSelection(Number(e.currentTarget.value))}
                  onBlur={(e) => commitInitializationSelection(Number(e.currentTarget.value))}
                  disabled={
                    initializationQuery.isLoading ||
                    (initializationQuery.data?.available_initialization_datetimes ?? []).length ===
                      0
                  }
                />
                {sliderTickCount > 0 && (
                  <div className="firo-trace-slider-ticks" aria-hidden="true">
                    {initializationOptions.map((_, index) => {
                      const leftPercent =
                        sliderTickCount === 1 ? 50 : (index / (sliderTickCount - 1)) * 100;
                      const transform =
                        index === 0
                          ? 'none'
                          : index === sliderTickCount - 1
                            ? 'translateX(-100%)'
                            : 'translateX(-50%)';

                      return (
                        <span
                          key={`initialization-tick-${index}`}
                          className="firo-trace-slider-tick"
                          style={{ left: `${leftPercent}%`, transform }}
                        />
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="firo-trace-plot-container mt-3">
          {(traceDataQuery.isFetching || isShowingPreviousTraceWhileUpdating) &&
            traceDataQuery.data && (
              <div className="firo-trace-plot-updating text-muted small">
                <Spinner animation="border" size="sm" className="me-2" />
                Updating trace data...
              </div>
            )}

          {traceDataQuery.isLoading && !traceDataQuery.data && (
            <div className="firo-trace-plot-state text-muted small">
              <Spinner animation="border" size="sm" className="me-2" />
              Loading trace data...
            </div>
          )}

          {traceDataQuery.isError && (
            <div className="firo-trace-plot-state">
              <Alert variant="danger" className="py-2 small mb-0 w-100">
                Failed to load trace data:{' '}
                {traceDataQuery.error instanceof Error
                  ? traceDataQuery.error.message
                  : 'Unknown error'}
              </Alert>
            </div>
          )}

          {traceDataQuery.data && (
            <div className="firo-trace-plot-canvas">
              <EventTracePlot data={traceDataQuery.data} />
            </div>
          )}

          {!traceThreshold && (
            <div className="firo-trace-plot-state text-center text-muted small">
              <p className="mb-0">Select a specific quantile to load trace data.</p>
            </div>
          )}
        </div>
      </Card.Body>
    </>
  );
};
