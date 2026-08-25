import { Form, Row, Col, Button } from 'react-bootstrap';
import MultiSelectDropdown from '@/shared/components/MultiSelectDropdown';
import { useConfigurations } from '@/shared/queries/configurations';
import { useVariables } from '@/shared/queries/variables';
import type { MapLocation } from '@/shared/types/locations';
import type { MapFilters } from '@/shared/types/maps';
import type { TimeseriesFilters, TimeseriesRequestFilters } from '@/shared/types/timeseries';
import {
  DURATION_NAME_TO_ISO,
  toDisplayVariableName,
  toPrimaryVariableName,
} from '@/shared/utils/durationUtils';

export type TimeseriesControlsProps = {
  table: string;
  timeseriesFilters: TimeseriesFilters;
  updateTimeseriesFilters: (patch: Partial<TimeseriesFilters>) => void;
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

  const handleVariableChange = (variable: string | null) => {
    if (!variable) return;
    updateTimeseriesFilters({
      primary: {
        ...primaryFilters,
        variables: [toPrimaryVariableName(variable)],
      },
      secondary: {
        ...secondaryFilters,
        variables: [variable],
      },
    });
  };

  const handleLoadData = async () => {
    if (!selectedLocation?.primary_location_id || !timeseriesFilters.secondary.variables[0]) return;

    setRequestFilters({
      primary_location_id: selectedLocation.primary_location_id,
      primary: primaryFilters,
      secondary: secondaryFilters,
    });

    // Switch to plot view after loading data
    if (onViewModeChange) {
      onViewModeChange('plot');
    }
  };

  // Get selected configurations or use map configuration as fallback
  const selectedConfigurations =
    !!timeseriesFilters.secondary.configurations &&
    timeseriesFilters.secondary.configurations?.length > 0
      ? timeseriesFilters.secondary.configurations
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
                onChange={(selected) => handleSecondaryFilterChange('configurations', selected)}
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
                value={timeseriesFilters.secondary.variables[0] || mapFilters.variable || ''}
                onChange={(e) => handleVariableChange(e.target.value || null)}
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
                value={timeseriesFilters.primary.duration || ''}
                disabled={
                  !(timeseriesFilters.secondary.variables[0] || mapFilters.variable)?.endsWith(
                    '_inst'
                  )
                }
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

          {/* Start Date */}
          <Col md={6}>
            <Form.Group>
              <Form.Label className="small fw-bold">Start Date</Form.Label>
              <Form.Control
                type="datetime-local"
                size="sm"
                value={timeseriesFilters.primary.start_date || ''}
                onChange={(e) => handlePrimaryFilterChange('start_date', e.target.value || null)}
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
                value={timeseriesFilters.primary.end_date || ''}
                onChange={(e) => handlePrimaryFilterChange('end_date', e.target.value || null)}
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
                value={timeseriesFilters.secondary.reference_start_date || ''}
                onChange={(e) =>
                  handleSecondaryFilterChange('reference_start_date', e.target.value || null)
                }
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
                value={timeseriesFilters.secondary.reference_end_date || ''}
                onChange={(e) =>
                  handleSecondaryFilterChange('reference_end_date', e.target.value || null)
                }
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
                  !timeseriesFilters.secondary.configurations?.length ||
                  !timeseriesFilters.secondary.variables[0]
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
