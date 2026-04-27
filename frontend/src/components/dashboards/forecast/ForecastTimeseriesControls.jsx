import { useMemo, useState } from 'react';
import { Form, Row, Col, Button, Tabs, Tab } from 'react-bootstrap';
import MultiSelectDropdown from '../../common/MultiSelectDropdown';

const ForecastTimeseriesControls = ({
  state,
  timeseriesFilters,
  updateTimeseriesFilters,
  loadTimeseries,
  selectedLocation,
  onViewModeChange
}) => {
  const [activeTab, setActiveTab] = useState('observations');

  const primaryFilters = useMemo(() => {
    const nested = timeseriesFilters?.primary || {};
    return {
      variables: nested.variables ?? (timeseriesFilters?.variable ? [timeseriesFilters.variable] : []),
      start_date: nested.start_date ?? timeseriesFilters?.start_date ?? null,
      end_date: nested.end_date ?? timeseriesFilters?.end_date ?? null
    };
  }, [timeseriesFilters]);

  const secondaryFilters = useMemo(() => {
    const nested = timeseriesFilters?.secondary || {};
    return {
      configurations: nested.configurations ?? timeseriesFilters?.configurations ?? [],
      variables: nested.variables ?? (timeseriesFilters?.variable ? [timeseriesFilters.variable] : []),
      reference_start_date: nested.reference_start_date ?? timeseriesFilters?.reference_start_date ?? null,
      reference_end_date: nested.reference_end_date ?? timeseriesFilters?.reference_end_date ?? null
    };
  }, [timeseriesFilters]);

  const handlePrimaryFilterChange = (field, value) => {
    updateTimeseriesFilters({
      primary: {
        ...primaryFilters,
        [field]: value
      }
    });
  };

  const handleSecondaryFilterChange = (field, value) => {
    updateTimeseriesFilters({
      secondary: {
        ...secondaryFilters,
        [field]: value
      }
    });
  };

  const canLoadTimeseries = Boolean(
    selectedLocation?.primary_location_id
    && primaryFilters.variables?.length
    && secondaryFilters.variables?.length
    && secondaryFilters.configurations?.length
  );

  const handleLoadData = async () => {
    if (!canLoadTimeseries) return;

    await loadTimeseries({
      primary_location_id: selectedLocation.primary_location_id,
      primary: primaryFilters,
      secondary: secondaryFilters
    });

    if (onViewModeChange) {
      onViewModeChange('plot');
    }
  };

  return (
    <div className="h-100 d-flex flex-column">
      <Form className="flex-grow-1 d-flex flex-column">
        <Tabs
          id="forecast-timeseries-filter-tabs"
          activeKey={activeTab}
          onSelect={(key) => setActiveTab(key || 'observations')}
          className="mb-3"
          justify
        >
          <Tab eventKey="observations" title="Observations (Primary)">
            <Row className="g-2">
              <Col md={12}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Variable</Form.Label>
                  <MultiSelectDropdown
                    options={Array.isArray(state.variables) ? state.variables : []}
                    selected={primaryFilters.variables}
                    onChange={(selected) => handlePrimaryFilterChange('variables', selected)}
                    allSelectedText="All variables"
                    noneSelectedText="Select variables..."
                  />
                </Form.Group>
              </Col>

              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Start Date</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    size="sm"
                    value={primaryFilters.start_date || ''}
                    onChange={(e) => handlePrimaryFilterChange('start_date', e.target.value || null)}
                  />
                </Form.Group>
              </Col>

              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">End Date</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    size="sm"
                    value={primaryFilters.end_date || ''}
                    onChange={(e) => handlePrimaryFilterChange('end_date', e.target.value || null)}
                  />
                </Form.Group>
              </Col>
            </Row>
          </Tab>

          <Tab eventKey="forecast" title="Forecast (Secondary)">
            <Row className="g-2">
              <Col md={12}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Configurations</Form.Label>
                  <MultiSelectDropdown
                    options={Array.isArray(state.configurations) ? state.configurations : []}
                    selected={secondaryFilters.configurations}
                    onChange={(selected) => handleSecondaryFilterChange('configurations', selected)}
                    allSelectedText="All configurations"
                    noneSelectedText="Select configurations..."
                  />
                </Form.Group>
              </Col>

              <Col md={12}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Variable</Form.Label>
                  <MultiSelectDropdown
                    options={Array.isArray(state.variables) ? state.variables : []}
                    selected={secondaryFilters.variables}
                    onChange={(selected) => handleSecondaryFilterChange('variables', selected)}
                    allSelectedText="All variables"
                    noneSelectedText="Select variables..."
                  />
                </Form.Group>
              </Col>

              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Reference Start Date</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    size="sm"
                    value={secondaryFilters.reference_start_date || ''}
                    onChange={(e) => handleSecondaryFilterChange('reference_start_date', e.target.value || null)}
                  />
                </Form.Group>
              </Col>

              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Reference End Date</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    size="sm"
                    value={secondaryFilters.reference_end_date || ''}
                    onChange={(e) => handleSecondaryFilterChange('reference_end_date', e.target.value || null)}
                  />
                </Form.Group>
              </Col>
            </Row>
          </Tab>
        </Tabs>

        <div className="d-flex justify-content-between align-items-center mt-auto pt-2 border-top">
          <div className="small text-muted">
            Configure observations and forecast independently, then load.
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={handleLoadData}
            disabled={!canLoadTimeseries}
          >
            Load Timeseries Data
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default ForecastTimeseriesControls;
