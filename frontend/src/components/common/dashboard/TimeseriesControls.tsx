import { Form, Row, Col, Button } from 'react-bootstrap';
import { useConfigurations } from '../../../shared/queries/configurations';
import { useVariables } from '../../../shared/queries/variables';
import type { MapLocation } from '../../../shared/types/locations';
import type { MapFilters } from '../../../shared/types/maps';
import type {
  TimeseriesFiltersFlat,
  TimeseriesRequestFilters,
} from '../../../shared/types/timeseries';
import {
  DURATION_NAME_TO_ISO,
  toDisplayVariableName,
  toPrimaryVariableName,
} from '../../../utils/durationUtils';
import MultiSelectDropdown from '../MultiSelectDropdown';

export type TimeseriesControlsProps = {
  table: string;
  timeseriesFilters: TimeseriesFiltersFlat;
  updateTimeseriesFilters: (patch: Partial<TimeseriesFiltersFlat>) => void;
  setRequestFilters: (filters: TimeseriesRequestFilters) => void;
  selectedLocation: MapLocation;
  mapFilters: MapFilters;
  onViewModeChange: (viewMode: string) => void;
};

const TimeseriesControls = ({
  table,
  timeseriesFilters,
  updateTimeseriesFilters,
  setRequestFilters,
  selectedLocation,
  mapFilters,
  onViewModeChange,
}: TimeseriesControlsProps) => {
  const configurations = useConfigurations(table);
  const variables = useVariables(table);

  const handleFilterChange = (field: string, value: unknown) => {
    updateTimeseriesFilters({ [field]: value });
  };

  const handleLoadData = async () => {
    if (!selectedLocation?.primary_location_id || !timeseriesFilters.variable) return;

    const primaryVariable = timeseriesFilters.variable?.endsWith('_inst')
      ? toPrimaryVariableName(timeseriesFilters.variable)
      : timeseriesFilters.variable;

    setRequestFilters({
      primary_location_id: selectedLocation.primary_location_id,
      primary: {
        variables: [primaryVariable],
        start_date: timeseriesFilters.start_date,
        end_date: timeseriesFilters.end_date,
        duration: timeseriesFilters.duration,
      },
      secondary: {
        configurations: timeseriesFilters.configurations,
        variables: [timeseriesFilters.variable],
        start_date: timeseriesFilters.start_date,
        end_date: timeseriesFilters.end_date,
        // Drop reference dates to match existing retrospective functionality
        // reference_start_date: timeseriesFilters.reference_start_date,
        // reference_end_date: timeseriesFilters.reference_end_date,
      },
    });

    // Switch to plot view after loading data
    if (onViewModeChange) {
      onViewModeChange('plot');
    }
  };

  // Get selected configurations or use map configuration as fallback
  const selectedConfigurations =
    !!timeseriesFilters.configurations && timeseriesFilters.configurations?.length > 0
      ? timeseriesFilters.configurations
      : mapFilters.configuration
        ? [mapFilters.configuration]
        : [];

  return (
    <div className="h-100 d-flex flex-column">
      <Form className="flex-grow-1">
        <Row className="g-2 align-content-start">
          {/* Configuration - Multi-select */}
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Configurations</Form.Label>
              <MultiSelectDropdown
                options={Array.isArray(configurations.data) ? configurations.data : []}
                selected={selectedConfigurations}
                onChange={(selected) => handleFilterChange('configurations', selected)}
                allSelectedText="All configurations"
                noneSelectedText="Select configurations..."
              />
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
                {Array.isArray(variables.data) &&
                  variables.data.map((variable: string) => (
                    <option key={variable} value={toDisplayVariableName(variable)}>
                      {variable}
                    </option>
                  ))}
              </Form.Select>
            </Form.Group>
          </Col>

          {/* Inst observations timestep */}
          <Col md={6}>
            <Form.Group>
              <Form.Label className="small fw-bold">Obs timestep (if available)</Form.Label>
              <Form.Select
                size="sm"
                value={timeseriesFilters.duration || ''}
                disabled={!(timeseriesFilters.variable || mapFilters.variable)?.endsWith('_inst')}
                onChange={(e) => handleFilterChange('duration', e.target.value)}
              >
                {Object.entries(DURATION_NAME_TO_ISO).map(([label, iso]) => (
                  <option key={iso} value={iso}>
                    {label}
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
                disabled={
                  !selectedLocation?.primary_location_id ||
                  !timeseriesFilters.configurations?.length ||
                  !timeseriesFilters.variable
                }
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
