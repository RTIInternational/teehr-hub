import { Form, Button, Row, Col, Spinner } from 'react-bootstrap';
import { useForecastDashboard } from '../../../context/ForecastDashboardContext.jsx';
import { useForecastFilters, useForecastLocationSelection } from '../../../hooks/useForecastDataFetching';
import { useForecastData } from './useForecastData';

const TimeseriesControls = () => {
  const { state } = useForecastDashboard();
  const { timeseriesFilters, updateTimeseriesFilters } = useForecastFilters();
  const { loadTimeseries } = useForecastData();
  const { selectedLocation } = useForecastLocationSelection();
  
  const handleTimeseriesFilterChange = (filterType, value) => {
    updateTimeseriesFilters({ [filterType]: value });
  };
  
  const handleLoadTimeseries = async () => {
    if (!selectedLocation) {
      alert('Please select a location first');
      return;
    }
    
    await loadTimeseries({
      location_id: selectedLocation.location_id,
      configuration: timeseriesFilters.configuration,
      variable: timeseriesFilters.variable,
      start_date: timeseriesFilters.start_date,
      end_date: timeseriesFilters.end_date,
      reference_start_date: timeseriesFilters.reference_start_date,
      reference_end_date: timeseriesFilters.reference_end_date
    });
  };

  return (
    <div style={{ padding: '20px' }}>
      <Form.Group className="mb-3">
        <Form.Label>Configuration</Form.Label>
        <Form.Select 
          size="sm" 
          value={timeseriesFilters.configuration || ''}
          onChange={(e) => handleTimeseriesFilterChange('configuration', e.target.value)}
        >
          <option value="">Select Configuration</option>
          {Array.isArray(state.configurations) ? state.configurations.map(config => (
            <option key={config} value={config}>{config}</option>
          )) : []}
        </Form.Select>
      </Form.Group>
      
      <Form.Group className="mb-3">
        <Form.Label>Variable</Form.Label>
        <Form.Select 
          size="sm" 
          value={timeseriesFilters.variable || ''}
          onChange={(e) => handleTimeseriesFilterChange('variable', e.target.value)}
        >
          <option value="">Select Variable</option>
          {Array.isArray(state.variables) ? state.variables.map(variable => (
            <option key={variable} value={variable}>{variable}</option>
          )) : []}
        </Form.Select>
      </Form.Group>
      
      <Form.Group className="mb-3">
        <Form.Label>Value Time Range (optional)</Form.Label>
        <Row>
          <Col xs={6}>
            <Form.Label className="small">Start Date</Form.Label>
            <Form.Control 
              type="datetime-local" 
              size="sm" 
              value={timeseriesFilters.start_date || ''}
              onChange={(e) => handleTimeseriesFilterChange('start_date', e.target.value)}
            />
          </Col>
          <Col xs={6}>
            <Form.Label className="small">End Date</Form.Label>
            <Form.Control 
              type="datetime-local" 
              size="sm" 
              value={timeseriesFilters.end_date || ''}
              onChange={(e) => handleTimeseriesFilterChange('end_date', e.target.value)}
            />
          </Col>
        </Row>
      </Form.Group>
      
      <Form.Group className="mb-3">
        <Form.Label>Reference Time Range (optional)</Form.Label>
        <Row>
          <Col xs={6}>
            <Form.Label className="small">Start Reference Time</Form.Label>
            <Form.Control 
              type="datetime-local" 
              size="sm" 
              value={timeseriesFilters.reference_start_date || ''}
              onChange={(e) => handleTimeseriesFilterChange('reference_start_date', e.target.value)}
            />
          </Col>
          <Col xs={6}>
            <Form.Label className="small">End Reference Time</Form.Label>
            <Form.Control 
              type="datetime-local" 
              size="sm" 
              value={timeseriesFilters.reference_end_date || ''}
              onChange={(e) => handleTimeseriesFilterChange('reference_end_date', e.target.value)}
            />
          </Col>
        </Row>
      </Form.Group>
      
      <div className="d-grid">
        <Button 
          variant="primary"
          onClick={handleLoadTimeseries}
          disabled={!selectedLocation || !timeseriesFilters.configuration || !timeseriesFilters.variable || state.timeseriesLoading}
        >
          {state.timeseriesLoading ? (
            <>
              <Spinner
                as="span"
                animation="border"
                size="sm"
                role="status"
                aria-hidden="true"
                className="me-2"
              />
              Loading...
            </>
          ) : (
            'Load Timeseries'
          )}
        </Button>
      </div>
    </div>
  );
};

export default TimeseriesControls;