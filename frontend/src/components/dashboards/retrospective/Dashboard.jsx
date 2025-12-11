import { useEffect } from 'react';
import { useRetrospectiveDashboard, ActionTypes } from '../../../context/RetrospectiveDashboardContext.jsx';
import { useRetrospectiveData } from './useRetrospectiveData';
import { 
  MapComponent, 
  TimeseriesComponent, 
  MapFilterButton, 
  TimeseriesControls 
} from '../../common/dashboard';
import { LocationMetrics, LocationCard } from '../../common';
import { getMetricLabel } from '../../common/dashboard/utils.js';
import { useRetrospectiveLocationSelection, useRetrospectiveFilters } from '../../../hooks/useRetrospectiveDataFetching';

const Dashboard = () => {
  const { state, dispatch } = useRetrospectiveDashboard();
  const { initializeRetrospectiveData } = useRetrospectiveData();
  const { selectLocation } = useRetrospectiveLocationSelection();
  const { loadLocations } = useRetrospectiveData();
  const { mapFilters, updateMapFilters, timeseriesFilters, updateTimeseriesFilters } = useRetrospectiveFilters();
  const { loadTimeseries, loadLocationMetrics } = useRetrospectiveData();
  const { selectedLocation } = useRetrospectiveLocationSelection();
  
  // Create dashboard-specific components with injected dependencies
  const RetrospectiveMapFilterButton = () => (
    <MapFilterButton
      state={state}
      mapFilters={mapFilters}
      updateMapFilters={updateMapFilters}
      loadLocations={loadLocations}
    />
  );
  
  const RetrospectiveTimeseriesControls = () => (
    <TimeseriesControls
      state={state}
      timeseriesFilters={timeseriesFilters}
      updateTimeseriesFilters={updateTimeseriesFilters}
      loadTimeseries={loadTimeseries}
      selectedLocation={selectedLocation}
    />
  );
  
  // Debug: Log state changes
  useEffect(() => {
    console.log('Dashboard state updated:', {
      configurationsLength: state.configurations?.length,
      variablesLength: state.variables?.length,
      metricsLength: state.metrics?.length,
      error: state.error
    });
  }, [state.configurations, state.variables, state.metrics, state.error]);
  
  // Load initial data when component mounts
  useEffect(() => {
    const initializeData = async () => {
      try {
        console.log('Dashboard: Starting data initialization...');
        await initializeRetrospectiveData();
        console.log('Dashboard: Data initialization completed');
      } catch (error) {
        console.error('Dashboard: Error during initialization:', error);
      }
    };
    
    initializeData();
  }, [initializeRetrospectiveData]);
  
  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100vh - 56px)' }}>
      {/* Height adjusted for navbar (Bootstrap navbar is typically 56px) */}
      
      <div className="container-fluid flex-grow-1 p-0">
        <div 
          className="dashboard-grid h-100" 
          style={{
            display: 'grid',
            gridTemplateColumns: '60% 40%',
            gridTemplateRows: 'auto 15vh 1fr 35vh',
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
          
          {/* Map Panel - Left Column, spans full height */}
          <div 
            className="map-panel" 
            style={{
              gridColumn: '1 / 2',
              gridRow: state.error ? '2 / 5' : '1 / 5',
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
              MapFilterButton={RetrospectiveMapFilterButton}
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
              gridRow: state.error ? '3 / 4' : '2 / 4',
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
                TimeseriesControls={RetrospectiveTimeseriesControls}
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

          {/* Metrics Panel - Bottom Right */}
          <div 
            className="metrics-panel" 
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '4 / 5' : '4 / 5',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'auto'
            }}
          >
            {state.selectedLocation ? (
              <LocationMetrics
                selectedLocation={state.selectedLocation}
                locationMetrics={state.locationMetrics}
                metricsLoading={state.metricsLoading}
                error={state.error}
                loadLocationMetrics={loadLocationMetrics}
              />
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