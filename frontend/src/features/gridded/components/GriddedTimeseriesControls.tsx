import { Button, Col, Form, Row } from 'react-bootstrap';

import DateRangeInputs from '@/shared/components/DateRangeInputs';
import MultiSelectDropdown from '@/shared/components/MultiSelectDropdown';
import { useDatasets } from '@/shared/queries/gridded/datasets';
import type { GriddedTimeseriesFilters } from '@/shared/types/gridded/timeseries';

import { DEFAULT_TIMESERIES_FILTERS, timeseriesDatasets } from '../DashboardContext';

export type GriddedTimeseriesControlsProps = {
  timeseriesFilters: GriddedTimeseriesFilters;
  updateTimeseriesFilters: (patch: Partial<GriddedTimeseriesFilters>) => void;
  activeDataset: string | null;
};

const GriddedTimeseriesControls = ({
  timeseriesFilters,
  updateTimeseriesFilters,
  activeDataset,
}: GriddedTimeseriesControlsProps) => {
  const datasets = useDatasets();
  const { start_date, end_date } = timeseriesFilters;

  const rangeError =
    start_date && end_date && start_date > end_date
      ? 'Start date must not be after end date.'
      : null;

  return (
    <div className="h-100 d-flex flex-column">
      <Form className="flex-grow-1 d-flex flex-column">
        <Row className="g-2">
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Datasets</Form.Label>
              <MultiSelectDropdown
                isLoading={datasets.isLoading}
                options={datasets.data}
                selected={timeseriesDatasets(timeseriesFilters, activeDataset)}
                onChange={(selected) => updateTimeseriesFilters({ datasets: selected })}
                allSelectedText="All datasets"
                noneSelectedText="Select datasets..."
              />
            </Form.Group>
          </Col>

          <DateRangeInputs
            start={start_date}
            end={end_date}
            onStartChange={(value) => updateTimeseriesFilters({ start_date: value })}
            onEndChange={(value) => updateTimeseriesFilters({ end_date: value })}
          />

          {rangeError && (
            <Col md={12}>
              <div className="small text-danger">{rangeError}</div>
            </Col>
          )}
        </Row>

        <div className="d-flex justify-content-between align-items-center mt-auto pt-2 border-top">
          <div className="small text-muted">
            Leave dates empty for up to 3 years before the map&apos;s date (max span 20 years).
          </div>
          <Button
            variant="outline-secondary"
            size="sm"
            onClick={() => updateTimeseriesFilters(DEFAULT_TIMESERIES_FILTERS)}
          >
            Reset
          </Button>
        </div>
      </Form>
    </div>
  );
};

export default GriddedTimeseriesControls;
