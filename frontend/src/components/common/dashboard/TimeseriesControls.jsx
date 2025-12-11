import { Form, Row, Col, Button } from 'react-bootstrap';

const TimeseriesControls = ({ 
  state, 
  timeseriesFilters, 
  updateTimeseriesFilters, 
  loadTimeseries, 
  selectedLocation,
  mapFilters
}) => {
  
  const handleFilterChange = (field, value) => {
    updateTimeseriesFilters({ [field]: value });
  };

  const handleLoadData = async () => {
    if (!selectedLocation?.location_id) return;
    
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
    <div className="h-100 d-flex flex-column">
      <Form className="flex-grow-1">
        <Row className="g-2 h-100">
          {/* Configuration */}
          <Col md={6}>
            <Form.Group>
              <Form.Label className="small fw-bold">Configuration</Form.Label>
            <Form.Select
              size="sm"
              value={timeseriesFilters.configuration || mapFilters.configuration || ''}
              onChange={(e) => handleFilterChange('configuration', e.target.value || null)}
            >
              <option value="">Select Configuration...</option>
              {Array.isArray(state.configurations) && state.configurations.map((config) => (
                <option key={config} value={config}>
                  {config}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
        </Col>

        {/* Variable */}
        <Col md={6}>
          <Form.Group>
            <Form.Label className="small fw-bold">Variable</Form.Label>
            <Form.Select
              size="sm"
              value={timeseriesFilters.variable || mapFilters.variable || ''}
              onChange={(e) => handleFilterChange('variable', e.target.value || null)}
            >
              <option value="">Select Variable...</option>
              {Array.isArray(state.variables) && state.variables.map((variable) => (
                <option key={variable} value={variable}>
                  {variable}
                </option>
              ))}
            </Form.Select>
          </Form.Group>
        </Col>

        {/* Start Date */}
        <Col md={6}>
          <Form.Group>
            <Form.Label className="small fw-bold">Start Date</Form.Label>
            <Form.Control
              type="datetime-local"
              size="sm"
              value={timeseriesFilters.start_date || ''}
              onChange={(e) => handleFilterChange('start_date', e.target.value || null)}
            />
          </Form.Group>
        </Col>

        {/* End Date */}
        <Col md={6}>
          <Form.Group>
            <Form.Label className="small fw-bold">End Date</Form.Label>
            <Form.Control
              type="datetime-local"
              size="sm"
              value={timeseriesFilters.end_date || ''}
              onChange={(e) => handleFilterChange('end_date', e.target.value || null)}
            />
          </Form.Group>
        </Col>

        {/* Reference Start Date */}
        <Col md={6}>
          <Form.Group>
            <Form.Label className="small fw-bold">Reference Start Date</Form.Label>
            <Form.Control
              type="datetime-local"
              size="sm"
              value={timeseriesFilters.reference_start_date || ''}
              onChange={(e) => handleFilterChange('reference_start_date', e.target.value || null)}
            />
          </Form.Group>
        </Col>

        {/* Reference End Date */}
        <Col md={6}>
          <Form.Group>
            <Form.Label className="small fw-bold">Reference End Date</Form.Label>
            <Form.Control
              type="datetime-local"
              size="sm"
              value={timeseriesFilters.reference_end_date || ''}
              onChange={(e) => handleFilterChange('reference_end_date', e.target.value || null)}
            />
          </Form.Group>
        </Col>

        {/* Load Button */}
        <Col md={12}>
          <div className="d-flex justify-content-end mt-2">
            <Button 
              variant="primary" 
              size="sm" 
              onClick={handleLoadData}
              disabled={!selectedLocation?.location_id || !timeseriesFilters.configuration || !timeseriesFilters.variable}
            >
              Load Timeseries Data
            </Button>
          </div>
        </Col>
        </Row>
      </Form>
    </div>
  );
};

export default TimeseriesControls;