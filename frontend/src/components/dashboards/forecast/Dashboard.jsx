import { useEffect } from 'react';
import { useForecastDashboard, ActionTypes } from '../../../context/ForecastDashboardContext.jsx';
import { useForecastData } from './useForecastData';
import { 
  MapComponent, 
  TimeseriesComponent, 
  MapFilterButton, 
  TimeseriesControls 
} from '../../common/dashboard';
import { LocationMetrics, LocationCard } from '../../common';
import { getMetricLabel } from '../../common/dashboard/utils.js';
import { useForecastLocationSelection, useForecastFilters } from '../../../hooks/useForecastDataFetching';

const Dashboard = () => {
  const { state, dispatch } = useForecastDashboard();
  const { initializeForecastData } = useForecastData();
  const { selectLocation } = useForecastLocationSelection();
  const { loadLocations } = useForecastData();
  const { mapFilters, updateMapFilters, timeseriesFilters, updateTimeseriesFilters } = useForecastFilters();
  const { loadTimeseries, loadLocationMetrics } = useForecastData();
  const { selectedLocation } = useForecastLocationSelection();
  
  // Create dashboard-specific components with injected dependencies
  const ForecastMapFilterButton = () => (
    <MapFilterButton
      state={state}
      mapFilters={mapFilters}
      updateMapFilters={updateMapFilters}
      loadLocations={loadLocations}
    />
  );
  
  const ForecastTimeseriesControls = () => (
    <TimeseriesControls
      state={state}
      timeseriesFilters={timeseriesFilters}
      updateTimeseriesFilters={updateTimeseriesFilters}
      loadTimeseries={loadTimeseries}
      selectedLocation={selectedLocation}
    />
  );
  
  // Load initial data when component mounts
  useEffect(() => {
    const initializeData = async () => {
      try {
        await initializeForecastData();
      } catch (error) {
        console.error('Forecast Dashboard: Error during initialization:', error);
      }
    };
    
    initializeData();
  }, [initializeForecastData]);
  
  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100vh - 56px)' }}>
      {/* Height adjusted for navbar (Bootstrap navbar is typically 56px) */}
      
      <div className="container-fluid flex-grow-1 p-0">
        <div 
          className="dashboard-grid h-100" 
          style={{
            display: 'grid',
            gridTemplateColumns: '60% 40%',
            gridTemplateRows: 'auto 12vh 1fr auto', // Changed last row to auto for flexible metrics height
            gap: '12px',
            padding: '12px',
            height: '100vh',
            overflow: 'hidden'
          }}
        >
          {/* Error Alert */}
          {state.error && (
            <div 
              className="alert alert-danger alert-dismissible" 
              role="alert" 
              style={{ 
                gridColumn: '1 / -1',
                gridRow: '1 / 2',
                zIndex: 1000,
                margin: 0
              }}
            >
              <i className="bi bi-exclamation-triangle-fill me-2"></i>
              <strong>Error:</strong> {state.error}
              <button 
                type="button" 
                className="btn-close" 
                onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })}
                aria-label="Close"
              ></button>
            </div>
          )}
          
          {/* Map Panel - Left Column, reduced height */}
          <div 
            className="map-panel" 
            style={{
              gridColumn: '1 / 2',
              gridRow: state.error ? '2 / 4' : '1 / 4', // Reduced from 5 to 4
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              position: 'relative'
            }}
          >
            <MapComponent
              state={state}
              dispatch={dispatch}
              ActionTypes={ActionTypes}
              selectLocation={selectLocation}
              loadLocations={loadLocations}
              MapFilterButton={ForecastMapFilterButton}
              getMetricLabel={getMetricLabel}
            />
          </div>

          {/* Location Info Card - Upper Right */}
          <div 
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '2 / 3' : '1 / 2'
            }}
          >
            <LocationCard 
              selectedLocation={state.selectedLocation}
              onClose={() => selectLocation(null)}
            />
          </div>

          {/* Timeseries Panel - Middle Right */}
          <div 
            className="timeseries-panel" 
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '3 / 4' : '2 / 4', // Keep same positioning
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden'
            }}
          >
            {state.selectedLocation ? (
              <TimeseriesComponent
                state={state}
                dispatch={dispatch}
                ActionTypes={ActionTypes}
                TimeseriesControls={ForecastTimeseriesControls}
              />
            ) : (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <div className="text-center">
                  <div style={{ fontSize: '3rem' }}>📈</div>
                  <h5>Select a Location</h5>
                  <p>Click on a location on the map to view its time series data.</p>
                </div>
              </div>
            )}
          </div>

          {/* Metrics Panel - Full Width Bottom */}
          <div 
            className="metrics-panel" 
            style={{
              gridColumn: '1 / -1', // Span full width
              gridRow: state.error ? '5 / 6' : '4 / 5', // Bottom row
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              height: '400px', // Fixed height instead of min/max
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            {state.selectedLocation ? (
              <LocationMetrics
                selectedLocation={state.selectedLocation}
                locationMetrics={state.locationMetrics}
                metricsLoading={state.metricsLoading}
                error={state.error}
                loadLocationMetrics={loadLocationMetrics}                tableProperties={state.tableProperties}
                defaultTable="fcst_metrics_by_location"              />
            ) : (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <div className="text-center">
                  <div style={{ fontSize: '2rem' }}>📊</div>
                  <h6>Metrics</h6>
                  <p className="small">Select a location to view metrics.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;