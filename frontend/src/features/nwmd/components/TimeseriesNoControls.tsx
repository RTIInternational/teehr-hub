import { Card, Spinner } from 'react-bootstrap';

import { usePrimaryTimeseries, useSecondaryTimeseries } from '@/shared/queries/timeseries';
import type { MapLocation } from '@/shared/types/locations';
import type { TimeseriesFilters } from '@/shared/types/timeseries';

import PlotlyChart from '../../../shared/components/PlotlyChart';

type TimeseriesNoControlsProps = {
  selectedLocation: MapLocation | null;
  timeseriesFilters: TimeseriesFilters;
};

const TimeseriesNoControls = ({
  selectedLocation,
  timeseriesFilters,
}: TimeseriesNoControlsProps) => {
  const primary_location_id = selectedLocation?.primary_location_id;
  const primary = usePrimaryTimeseries({ primary_location_id, ...timeseriesFilters });
  const secondary = useSecondaryTimeseries({ primary_location_id, ...timeseriesFilters });

  const primaryData = primary.data ?? [];
  const secondaryData = secondary.data ?? [];

  const hasData = primaryData.length > 0 || secondaryData.length > 0;

  return (
    <Card className="shadow-lg h-100 d-flex flex-column" style={{ borderRadius: '8px' }}>
      <Card.Body className="p-0 d-flex flex-column flex-grow-1 overflow-hidden">
        {!selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
            <div className="text-center">
              <div style={{ fontSize: '3rem' }}>📍</div>
              <h5>Select a Location</h5>
              <p>Click on a location on the map to view its time series data.</p>
            </div>
          </div>
        ) : primary.isLoading || secondary.isLoading ? (
          <div className="d-flex justify-content-center align-items-center flex-grow-1">
            <div className="text-center">
              <Spinner animation="border" variant="primary" />
              <div className="mt-2 small text-muted">Loading timeseries data...</div>
            </div>
          </div>
        ) : (
          <>
            {hasData ? (
              <div className="flex-grow-1 p-2" style={{ overflow: 'hidden', minHeight: 0 }}>
                <PlotlyChart
                  selectedLocation={selectedLocation}
                  primaryData={primaryData}
                  secondaryData={secondaryData}
                  height="100%"
                  allowForecastSelect={true}
                  showLegend={false}
                />
              </div>
            ) : (
              <div className="d-flex align-items-center justify-content-center flex-grow-1">
                <div className="text-center text-muted">
                  <div style={{ fontSize: '2rem' }}>📊</div>
                  <h6>No Data Available</h6>
                  <p className="small">
                    Try switching to Filters to adjust the time range or check if data exists for
                    this location.
                  </p>
                </div>
              </div>
            )}
          </>
        )}
      </Card.Body>
    </Card>
  );
};

export default TimeseriesNoControls;
