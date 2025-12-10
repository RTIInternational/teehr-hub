import { Card, Row, Col, Spinner, CloseButton } from 'react-bootstrap';
import { PlotlyChart } from '../../common';

const TimeseriesComponent = ({ 
  state, 
  dispatch, 
  ActionTypes, 
  TimeseriesControls 
}) => {
  const hasData = state.timeseriesData.primary?.length > 0 || state.timeseriesData.secondary?.length > 0;
  const shouldShowPlot = hasData && !state.timeseriesLoading;
  
  const handleClose = () => {
    dispatch({ type: ActionTypes.SELECT_LOCATION, payload: null });
  };
  
  return (
    <Card className="shadow-lg" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center">
        <Card.Title as="h6" className="mb-0">📍 Location Details</Card.Title>
        <CloseButton 
          aria-label="Close"
          onClick={handleClose}
        />
      </Card.Header>
      <Card.Body className="p-3">
        {!state.selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center" style={{ height: '400px' }}>
            <div className="text-center text-muted">
              <div style={{ fontSize: '3rem' }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view its details and time series data.</p>
            </div>
          </div>
        ) : (
          <>
            {/* Location Header */}
            <Row className="mb-3">
              <Col>
                <h6 className="mb-1">{state.selectedLocation.name}</h6>
                <small className="text-muted">
                  ID: {state.selectedLocation.location_id} | 
                  Coordinates: {state.selectedLocation.coordinates?.[1]?.toFixed(4)}, {state.selectedLocation.coordinates?.[0]?.toFixed(4)}
                </small>
              </Col>
            </Row>
            
            {/* Show either Chart/Loading or Controls, but not both */}
            {shouldShowPlot ? (
              <div style={{ height: '100%', overflow: 'hidden' }}>
                <PlotlyChart 
                  primaryData={state.timeseriesData.primary}
                  secondaryData={state.timeseriesData.secondary}
                  height="100%"
                />
              </div>
            ) : state.timeseriesLoading ? (
              <div className="d-flex justify-content-center align-items-center" style={{ height: '300px' }}>
                <div className="text-center">
                  <Spinner animation="border" variant="primary" />
                  <div className="mt-2 small text-muted">Loading timeseries data...</div>
                </div>
              </div>
            ) : hasData ? (
              <div className="d-flex align-items-center justify-content-center" style={{ height: '300px' }}>
                <div className="text-center text-muted">
                  <div style={{ fontSize: '2rem' }}>📊</div>
                  <h6>No Data Available</h6>
                  <p className="small">Try adjusting the time range or checking if data exists for this location.</p>
                </div>
              </div>
            ) : (
              <TimeseriesControls />
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesComponent;