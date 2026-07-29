import { useEffect } from 'react';
import { Card } from 'react-bootstrap';
import { useFIRODashboard, ActionTypes } from '../../../context/FIRODashboardContext.jsx';
import { useFIRODataFetching, useFIROFilters, useFIROLocationSelection } from '../../../hooks/useFIRODataFetching';
import { LocationCard, LocationMetrics } from '../../common';
import { MapComponent, MapFilterButton, TimeseriesComponent, TimeseriesControls } from '../../common/dashboard';
import { getMetricLabel } from '../../common/dashboard/utils.js';
import EventViewer from './EventViewer';
import EventHeatmap from './EventHeatmap';
import EnsemblePerformance from './EnsemblePerformance';

const Dashboard = () => {
  const { state, dispatch } = useFIRODashboard();
  const { initializeData, loadLocations, loadTimeseries, loadLocationMetrics, loadFIROSupplementaryData } = useFIRODataFetching();
  const { selectLocation, selectedLocation } = useFIROLocationSelection();
  const { mapFilters, updateMapFilters, timeseriesFilters, updateTimeseriesFilters } = useFIROFilters();

  const FIROMapFilterButton = () => (
    <MapFilterButton
      state={state}
      mapFilters={mapFilters}
      updateMapFilters={updateMapFilters}
      loadLocations={loadLocations}
    />
  );

  const FIROTimeseriesControls = ({ onViewModeChange }) => (
    <TimeseriesControls
      state={state}
      timeseriesFilters={timeseriesFilters}
      updateTimeseriesFilters={updateTimeseriesFilters}
      loadTimeseries={loadTimeseries}
      selectedLocation={selectedLocation}
      onViewModeChange={onViewModeChange}
      mapFilters={mapFilters}
    />
  );

  useEffect(() => {
    const initialize = async () => {
      try {
        await initializeData();
      } catch (error) {
        console.error('FIRO Dashboard: initialization failed', error);
      }
    };

    initialize();
  }, [initializeData]);

  useEffect(() => {
    if (!state.selectedLocation?.primary_location_id) return;
    loadFIROSupplementaryData(state.selectedLocation.primary_location_id, {
      configuration_name: state.mapFilters.configuration,
      variable_name: state.mapFilters.variable,
    });
  }, [state.selectedLocation?.primary_location_id, state.mapFilters.configuration, state.mapFilters.variable, loadFIROSupplementaryData]);

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)', minHeight: 0 }}>
      <div className="container-fluid flex-grow-1 p-0" style={{ minHeight: 0, overflow: 'hidden' }}>
        <div
          className="dashboard-grid h-100"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gridTemplateRows: 'auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.2fr) minmax(0, 1fr) minmax(0, 1fr)',
            gap: '12px',
            padding: '12px',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {state.error && (
            <div className="alert alert-danger alert-dismissible" role="alert" style={{ gridColumn: '1 / -1', gridRow: '1 / 2', zIndex: 1000, margin: 0 }}>
              <i className="bi bi-exclamation-triangle-fill me-2"></i>
              <strong>Error:</strong> {state.error}
              <button type="button" className="btn-close" onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })} aria-label="Close"></button>
            </div>
          )}

          <div className="map-panel" style={{ gridColumn: '1 / 2', gridRow: state.error ? '2 / 4' : '1 / 4', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', position: 'relative', minHeight: 0 }}>
            <MapComponent
              state={state}
              dispatch={dispatch}
              ActionTypes={ActionTypes}
              selectLocation={selectLocation}
              loadLocations={loadLocations}
              MapFilterButton={FIROMapFilterButton}
              getMetricLabel={getMetricLabel}
            />
          </div>

          <div style={{ gridColumn: '2 / 3', gridRow: state.error ? '2 / 3' : '1 / 2', minHeight: 0 }}>
            <LocationCard selectedLocation={state.selectedLocation} onClose={() => selectLocation(null)} />
          </div>

          <div className="timeseries-panel" style={{ gridColumn: '2 / 3', gridRow: state.error ? '3 / 4' : '2 / 4', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', minHeight: 0 }}>
            {state.selectedLocation ? (
              <TimeseriesComponent state={state} TimeseriesControls={FIROTimeseriesControls} />
            ) : (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <div className="text-center">
                  <div style={{ fontSize: '3rem' }}>📈</div>
                  <h5>Select a Location</h5>
                  <p>Click on a location on the map to view FIRO timeseries data.</p>
                </div>
              </div>
            )}
          </div>

          <div className="metrics-panel" style={{ gridColumn: '1 / -1', gridRow: state.error ? '5 / 6' : '4 / 5', border: '1px solid #e0e0e0', borderRadius: '8px', minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            {state.selectedLocation ? (
              <LocationMetrics
                selectedLocation={state.selectedLocation}
                locationMetrics={state.locationMetrics}
                metricsLoading={state.metricsLoading}
                error={state.error}
                loadLocationMetrics={loadLocationMetrics}
                tableProperties={state.tableProperties}
                defaultTable="locations_metrics"
              />
            ) : (
              <Card className="shadow-lg h-100" style={{ borderRadius: '8px', border: 'none' }}>
                <Card.Body className="d-flex align-items-center justify-content-center text-muted">
                  <div className="text-center">
                    <div style={{ fontSize: '2rem' }}>📊</div>
                    <h6>FIRO Metrics</h6>
                    <p className="small">Select a location to view metrics.</p>
                  </div>
                </Card.Body>
              </Card>
            )}
          </div>

          <div style={{ gridColumn: '1 / 2', gridRow: state.error ? '6 / 7' : '5 / 6', minHeight: 0 }}>
            <EventViewer
              selectedLocation={state.selectedLocation}
              mapFilters={state.mapFilters}
              eventRankings={state.eventRankings}
              joinedTimeseries={state.joinedTimeseries}
              loading={state.timeseriesLoading}
              error={state.error}
            />
          </div>

          <div style={{ gridColumn: '2 / 3', gridRow: state.error ? '6 / 7' : '5 / 6', minHeight: 0 }}>
            <EventHeatmap
              selectedLocation={state.selectedLocation}
              eventHeatmap={state.eventHeatmap}
              loading={state.metricsLoading}
              error={state.error}
            />
          </div>

          <div style={{ gridColumn: '1 / -1', gridRow: state.error ? '7 / 8' : '6 / 7', minHeight: 0 }}>
            <EnsemblePerformance
              selectedLocation={state.selectedLocation}
              joinedTimeseries={state.joinedTimeseries}
              loading={state.timeseriesLoading}
              error={state.error}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
