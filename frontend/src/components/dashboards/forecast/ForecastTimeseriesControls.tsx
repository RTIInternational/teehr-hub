import { useState } from 'react';
import { Form, Row, Col, Button, Tabs, Tab } from 'react-bootstrap';
import { useConfigurations } from '../../../shared/queries/configurations';
import { useVariables } from '../../../shared/queries/variables';
import type { MapLocation } from '../../../shared/types/locations';
import type { MapFilters } from '../../../shared/types/maps';
import type { TimeseriesFilters, TimeseriesRequestFilters } from '../../../shared/types/timeseries';
import {
  toDisplayVariableName,
  fromDisplayVariableName,
  isTimestepVariable,
  DURATION_NAME_TO_ISO,
} from '../../../utils/durationUtils';
import MultiSelectDropdown from '../../common/MultiSelectDropdown';

export type ForecastTimeseriesControlsProps = {
  table: string;
  timeseriesFilters: TimeseriesFilters;
  updateTimeseriesFilters: (patch: Partial<TimeseriesFilters>) => void;
  setRequestFilters: (filters: TimeseriesRequestFilters) => void;
  selectedLocation: MapLocation;
  mapFilters: MapFilters;
  onViewModeChange: (viewMode: string) => void;
};

const ForecastTimeseriesControls = ({
  table,
  timeseriesFilters,
  updateTimeseriesFilters,
  setRequestFilters,
  selectedLocation,
  onViewModeChange,
}: ForecastTimeseriesControlsProps) => {
  const [activeTab, setActiveTab] = useState('observations');

  const configurations = useConfigurations(table);
  const variables = useVariables(table);
  const primaryVariables = useVariables('primary_timeseries');

  const primaryFilters = timeseriesFilters.primary;
  const secondaryFilters = timeseriesFilters.secondary;

  const handlePrimaryFilterChange = (field: string, value: unknown) => {
    updateTimeseriesFilters({
      primary: {
        ...primaryFilters,
        [field]: value,
      },
    });
  };

  const handleSecondaryFilterChange = (field: string, value: unknown) => {
    updateTimeseriesFilters({
      secondary: {
        ...secondaryFilters,
        [field]: value,
      },
    });
  };

  const canLoadTimeseries = Boolean(
    selectedLocation?.primary_location_id &&
    primaryFilters.variables?.length &&
    secondaryFilters.variables?.length &&
    secondaryFilters.configurations?.length
  );

  const handleLoadData = async () => {
    if (!canLoadTimeseries) return;

    setRequestFilters({
      primary_location_id: selectedLocation.primary_location_id,
      primary: primaryFilters,
      secondary: secondaryFilters,
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
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Variable</Form.Label>
                  <MultiSelectDropdown
                    options={(Array.isArray(primaryVariables.data)
                      ? primaryVariables.data
                      : []
                    ).map(toDisplayVariableName)}
                    selected={(primaryFilters.variables || []).map(toDisplayVariableName)}
                    onChange={(displaySelected) =>
                      handlePrimaryFilterChange(
                        'variables',
                        displaySelected.map(fromDisplayVariableName)
                      )
                    }
                    allSelectedText="All variables"
                    noneSelectedText="Select variables..."
                  />
                </Form.Group>
              </Col>
              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Obs timestep (if available)</Form.Label>
                  <Form.Select
                    size="sm"
                    value={primaryFilters.duration || ''}
                    disabled={!(primaryFilters.variables || []).some(isTimestepVariable)}
                    onChange={(e) => handlePrimaryFilterChange('duration', e.target.value)}
                  >
                    {Object.entries(DURATION_NAME_TO_ISO).map(([label, iso]) => (
                      <option key={iso} value={iso}>
                        {label}
                      </option>
                    ))}
                  </Form.Select>
                </Form.Group>
              </Col>

              <Col md={6}>
                <Form.Group>
                  <Form.Label className="small fw-bold">Start Date</Form.Label>
                  <Form.Control
                    type="datetime-local"
                    size="sm"
                    value={primaryFilters.start_date || ''}
                    onChange={(e) =>
                      handlePrimaryFilterChange('start_date', e.target.value || null)
                    }
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
                    options={Array.isArray(configurations.data) ? configurations.data : []}
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
                    options={Array.isArray(variables.data) ? variables.data : []}
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
                    onChange={(e) =>
                      handleSecondaryFilterChange('reference_start_date', e.target.value || null)
                    }
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
                    onChange={(e) =>
                      handleSecondaryFilterChange('reference_end_date', e.target.value || null)
                    }
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
