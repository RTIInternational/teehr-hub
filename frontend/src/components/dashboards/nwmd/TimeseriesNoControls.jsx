import { useEffect } from "react";
import { Card, Spinner } from "react-bootstrap";
import { PlotlyChart } from "../../common";

const TimeseriesNoControls = ({
  selectedLocation,
  timeseriesFilters,
  timeseriesData,
  timeseriesLoading,
  loadTimeseries,
}) => {
  const hasData =
    timeseriesData.primary?.length > 0 || timeseriesData.secondary?.length > 0;

  useEffect(() => {
    const id = selectedLocation?.primary_location_id;
    if (!id) return;

    const { primary, secondary } = timeseriesFilters;
    if (
      !primary?.variables?.length ||
      !secondary?.variables?.length ||
      !secondary?.configurations?.length
    ) {
      console.warn("Missing required timeseries filters. Skipping auto-load.");
      return;
    }

    loadTimeseries({
      primary_location_id: id,
      primary: {
        variables: timeseriesFilters.primary?.variables,
        start_date: timeseriesFilters.primary?.start_date,
        end_date: timeseriesFilters.primary?.end_date,
      },
      secondary: {
        configurations: timeseriesFilters.secondary?.configurations,
        variables: timeseriesFilters.secondary?.variables,
        reference_start_date: timeseriesFilters.secondary?.reference_start_date,
        reference_end_date: timeseriesFilters.secondary?.reference_end_date,
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    selectedLocation?.primary_location_id,
    timeseriesFilters.primary?.variables,
    timeseriesFilters.primary?.start_date,
    timeseriesFilters.primary?.end_date,
    timeseriesFilters.secondary?.configurations,
    timeseriesFilters.secondary?.variables,
    timeseriesFilters.secondary?.reference_start_date,
    timeseriesFilters.secondary?.reference_end_date,
    loadTimeseries,
  ]);

  return (
    <Card
      className="shadow-lg h-100 d-flex flex-column"
      style={{ borderRadius: "8px" }}
    >
      <Card.Body className="p-0 d-flex flex-column flex-grow-1 overflow-hidden">
        {!selectedLocation ? (
          <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
            <div className="text-center">
              <div style={{ fontSize: "3rem" }}>📍</div>
              <h5>Select a Location</h5>
              <p>
                Click on a location on the map to view its time series data.
              </p>
            </div>
          </div>
        ) : timeseriesLoading ? (
          <div className="d-flex justify-content-center align-items-center flex-grow-1">
            <div className="text-center">
              <Spinner animation="border" variant="primary" />
              <div className="mt-2 small text-muted">
                Loading timeseries data...
              </div>
            </div>
          </div>
        ) : (
          <>
            {hasData ? (
              <div
                className="flex-grow-1 p-2"
                style={{ overflow: "hidden", minHeight: 0 }}
              >
                <PlotlyChart
                  primaryData={timeseriesData.primary}
                  secondaryData={timeseriesData.secondary}
                  height="100%"
                />
              </div>
            ) : (
              <div className="d-flex align-items-center justify-content-center flex-grow-1">
                <div className="text-center text-muted">
                  <div style={{ fontSize: "2rem" }}>📊</div>
                  <h6>No Data Available</h6>
                  <p className="small">
                    Try switching to Filters to adjust the time range or check
                    if data exists for this location.
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
