import { Card, Spinner, ButtonGroup, Button } from 'react-bootstrap';
import { PlotlyChart } from '../../common';
import { useState } from 'react';

const TimeseriesComponent = ({ 
  state, 
  dispatch, 
  ActionTypes, 
  TimeseriesControls 
}) => {
  const [viewMode, setViewMode] = useState('filters');
  const hasData = state.timeseriesData.primary?.length > 0 || state.timeseriesData.secondary?.length > 0;
  const shouldShowPlot = hasData && !state.timeseriesLoading;
  
  return (
    <Card className="shadow-lg h-100 d-flex flex-column" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center flex-shrink-0">
        <div className="d-flex align-items-center gap-2">
          <Card.Title as="h6" className="mb-0">📈 Time Series</Card.Title>
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
        ) : (
          <>
            {/* Show content based on view mode */}
            {viewMode === 'plot' ? (
              shouldShowPlot ? (
                <div className="flex-grow-1 p-2" style={{ overflow: 'hidden', minHeight: 0 }}>
                  <PlotlyChart 
                    primaryData={state.timeseriesData.primary}
                    secondaryData={state.timeseriesData.secondary}
                    height="100%"
                  />
                </div>
              ) : state.timeseriesLoading ? (
                <div className="d-flex justify-content-center align-items-center flex-grow-1">
                  <div className="text-center">
                    <Spinner animation="border" variant="primary" />
                    <div className="mt-2 small text-muted">Loading timeseries data...</div>
                  </div>
                </div>
              ) : (
                <div className="d-flex align-items-center justify-content-center flex-grow-1">
                  <div className="text-center text-muted">
                    <div style={{ fontSize: '2rem' }}>📊</div>
                    <h6>No Data Available</h6>
                    <p className="small">Try switching to Filters to adjust the time range or check if data exists for this location.</p>
                  </div>
                </div>
              )
            ) : (
              <div className="p-3 flex-grow-1 overflow-auto">
                <TimeseriesControls onViewModeChange={setViewMode} />
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesComponent;