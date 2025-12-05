import { Card, Row, Col, Spinner, CloseButton } from 'react-bootstrap';
import { useDashboard } from '../context/DashboardContext.jsx';
import { ActionTypes } from '../context/DashboardContext.jsx';
import PlotlyChart from './PlotlyChart.jsx';
import TimeseriesControls from './TimeseriesControls.jsx';

const TimeseriesComponent = () => {
  const { state, dispatch } = useDashboard();
  
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
              <p>Click on a location on the map to view timeseries data</p>
            </div>
          </div>
        ) : (
          <>
            {/* Location Information - Always shown when location is selected */}
            <div className="mb-3">
              <h6 className="text-primary mb-2">🎯 Selected Location</h6>
              <Row className="g-2 small">
                <Col xs={6}>
                  <span className="text-muted">Location ID:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.location_id}</span>
                </Col>
                <Col xs={6}>
                  <span className="text-muted">Latitude:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.coordinates?.[1]?.toFixed(4)}</span>
                </Col>
                <Col xs={12}>
                  <span className="text-muted">Name:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.name}</span>
                </Col>
                <Col xs={6}>
                  <span className="text-muted">Longitude:</span>
                  <span className="fw-bold ms-1">{state.selectedLocation.coordinates?.[0]?.toFixed(4)}</span>
                </Col>
              </Row>
            </div>
            <hr className="my-3" />
            
            {/* Content Area - Controls or Plot */}
            {state.timeseriesLoading ? (
              <div className="d-flex align-items-center justify-content-center" style={{ height: '400px' }}>
                <div className="text-center">
                  <Spinner animation="border" variant="primary" className="mb-3" />
                  <h5>Loading Timeseries Data</h5>
                </div>
              </div>
            ) : !shouldShowPlot ? (
              <TimeseriesControls />
            ) : (
              <PlotlyChart 
                primaryData={state.timeseriesData.primary}
                secondaryData={state.timeseriesData.secondary}
                selectedLocation={state.selectedLocation}
                filters={state.timeseriesFilters}
              />
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesComponent;