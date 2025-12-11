import { Card, Spinner } from 'react-bootstrap';
import { PlotlyChart } from '../../common';

const TimeseriesComponent = ({ 
  state, 
  dispatch, 
  ActionTypes, 
  TimeseriesControls 
}) => {
  const hasData = state.timeseriesData.primary?.length > 0 || state.timeseriesData.secondary?.length > 0;
  const shouldShowPlot = hasData && !state.timeseriesLoading;
  
  return (
    <Card className="shadow-lg h-100 d-flex flex-column" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center flex-shrink-0">
        <Card.Title as="h6" className="mb-0">📈 Time Series</Card.Title>
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
            {/* Show either Chart/Loading or Controls, but not both */}
            {shouldShowPlot ? (
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
            ) : hasData ? (
              <div className="d-flex align-items-center justify-content-center flex-grow-1">
                <div className="text-center text-muted">
                  <div style={{ fontSize: '2rem' }}>📊</div>
                  <h6>No Data Available</h6>
                  <p className="small">Try adjusting the time range or checking if data exists for this location.</p>
                </div>
              </div>
            ) : (
              <div className="p-3 flex-grow-1 overflow-auto">
                <TimeseriesControls />
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesComponent;