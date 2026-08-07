import React, { useState } from 'react';
import { Card, Spinner, ButtonGroup, Button } from 'react-bootstrap';
import { usePrimaryTimeseries, useSecondaryTimeseries } from '../../../shared/queries/timeseries';
import type { TimeseriesFilters, TimeseriesState } from '../../../shared/types/timeseries';
import { PlotlyChart } from '../../common';

type TimeseriesControlInjectedProps = {
  setRequestFilters: (filters: TimeseriesFilters) => void;
  onViewModeChange: (viewMode: string) => void;
};

type TimeseriesComponentProps<TControlsProps extends object> = {
  state: TimeseriesState;
  Controls: React.ComponentType<TControlsProps & TimeseriesControlInjectedProps>;
  controlsProps: TControlsProps;
};

const TimeseriesComponent = <TControlsProps extends object>({
  state,
  Controls,
  controlsProps,
}: TimeseriesComponentProps<TControlsProps>) => {
  const [viewMode, setViewMode] = useState('filters');
  const [requestFilters, setRequestFilters] = useState<TimeseriesFilters>();
  const primary = usePrimaryTimeseries(requestFilters);
  const secondary = useSecondaryTimeseries(requestFilters);

  const primaryData = primary.data ?? [];
  const secondaryData = secondary.data ?? [];

  const hasData = primaryData.length > 0 || secondaryData.length > 0;

  return (
    <Card className="shadow-lg h-100 d-flex flex-column" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center flex-shrink-0">
        <div className="d-flex align-items-center gap-2">
          <Card.Title as="h6" className="mb-0">
            📈 Time Series
          </Card.Title>
          {state.selectedLocation && (
            <ButtonGroup size="sm">
              <Button
                variant={viewMode === 'filters' ? 'primary' : 'outline-primary'}
                onClick={() => setViewMode('filters')}
                style={{ fontSize: '11px' }}
              >
                🔍 Filters
              </Button>
              <Button
                variant={viewMode === 'plot' ? 'primary' : 'outline-primary'}
                onClick={() => setViewMode('plot')}
                style={{ fontSize: '11px' }}
              >
                📈 Plot
              </Button>
            </ButtonGroup>
          )}
        </div>
      </Card.Header>
      <Card.Body className="p-0 d-flex flex-column flex-grow-1 overflow-hidden">
        {!state.selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
            <div className="text-center">
              <div style={{ fontSize: '3rem' }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view its time series data.</p>
            </div>
          </div>
        ) : primary.isLoading || secondary.isLoading ? (
          <div className="d-flex justify-content-center align-items-center flex-grow-1">
            <div className="text-center">
              <Spinner animation="border" variant="primary" />
              <div className="mt-2 small text-muted">Loading timeseries data...</div>
            </div>
          </div>
        ) : (
          <>
            {/* Show content based on view mode */}
            {viewMode === 'plot' ? (
              hasData ? (
                <div className="flex-grow-1 p-2" style={{ overflow: 'hidden', minHeight: 0 }}>
                  <PlotlyChart
                    primaryData={primaryData}
                    secondaryData={secondaryData}
                    selectedLocation={state.selectedLocation}
                    filters={state.timeseriesFilters}
                    height="100%"
                  />
                </div>
              ) : (
                <div className="d-flex align-items-center justify-content-center flex-grow-1">
                  <div className="text-center text-muted">
                    <div style={{ fontSize: '2rem' }}>📊</div>
                    <h6>No Data Available</h6>
                    <p className="small">
                      Try switching to Filters to adjust the time range or check if data exists for
                      this location.
                    </p>
                  </div>
                </div>
              )
            ) : (
              <div className="p-3 flex-grow-1 overflow-auto">
                <Controls
                  {...controlsProps}
                  setRequestFilters={setRequestFilters}
                  onViewModeChange={setViewMode}
                />
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesComponent;
