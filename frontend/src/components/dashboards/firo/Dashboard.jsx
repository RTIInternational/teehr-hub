import { useEffect } from 'react';
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
    <div style={{ overflowY: 'auto', height: 'calc(100dvh - 56px)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px' }}>

        {state.error && (
          <div className="alert alert-danger alert-dismissible" role="alert" style={{ margin: 0 }}>
            <i className="bi bi-exclamation-triangle-fill me-2"></i>
            <strong>Error:</strong> {state.error}
            <button type="button" className="btn-close" onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })} aria-label="Close"></button>
          </div>
        )}

        {/* ── Row 1: Map + Location card + Timeseries ───────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: 'auto minmax(0, 1fr)', gap: '12px', height: '60vh', minHeight: '480px' }}>
          <div style={{ gridColumn: '1 / 2', gridRow: '1 / 3', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', position: 'relative' }}>
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
          <div style={{ gridColumn: '2 / 3', gridRow: '1 / 2' }}>
            <LocationCard selectedLocation={state.selectedLocation} onClose={() => selectLocation(null)} />
          </div>
          <div style={{ gridColumn: '2 / 3', gridRow: '2 / 3', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden' }}>
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
        </div>

        {/* ── Row 2: Location Metrics ────────────────────────────────────── */}
        <div style={{ height: '55vh', minHeight: '400px', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
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
            <div className="d-flex align-items-center justify-content-center h-100 text-muted">
              <div className="text-center">
                <div style={{ fontSize: '2rem' }}>📊</div>
                <p className="small mb-0">Select a location to view FIRO metrics.</p>
              </div>
            </div>
          )}
        </div>

        {/* ── Row 3: Event Viewer + Event Heatmap ───────────────────────── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', height: '55vh', minHeight: '400px' }}>
          <div style={{ overflow: 'hidden' }}>
            <EventViewer
              selectedLocation={state.selectedLocation}
              mapFilters={state.mapFilters}
              eventRankings={state.eventRankings}
              joinedTimeseries={state.joinedTimeseries}
              loading={state.timeseriesLoading}
              error={state.error}
            />
          </div>
          <div style={{ overflow: 'hidden' }}>
            <EventHeatmap
              selectedLocation={state.selectedLocation}
              eventHeatmap={state.eventHeatmap}
              loading={state.metricsLoading}
              error={state.error}
            />
          </div>
        </div>

        {/* ── Row 4: Ensemble Performance ───────────────────────────────── */}
        <div style={{ height: '55vh', minHeight: '400px', overflow: 'hidden' }}>
          <EnsemblePerformance
            selectedLocation={state.selectedLocation}
            joinedTimeseries={state.joinedTimeseries}
            loading={state.timeseriesLoading}
            error={state.error}
          />
        </div>

      </div>
    </div>
  );
};

export default Dashboard;

