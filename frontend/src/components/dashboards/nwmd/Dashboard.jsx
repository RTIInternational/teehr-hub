import { useCallback, useEffect } from 'react';
import { useNwmdDashboard, ActionTypes } from '../../../context/NwmdDashboardContext.jsx';
import { useNwmdLocationSelection, useNwmdFilters } from '../../../hooks/useNwmdDataFetching';
import { LocationMetrics, LocationCard } from '../../common';
import {
  TimeseriesComponent, 
} from '../../common/dashboard';
import { getMetricLabel } from '../../common/dashboard/utils.js';
import { useNwmdData } from './useNwmdData';
import { NwmdMapComponent } from './NwmdMapComponent.jsx'
import { FilterSidebar } from './FilterSidebar.jsx';
import { CdfPlot } from './CdfPlot.jsx';

const Dashboard = () => {
  const { state, dispatch } = useNwmdDashboard();
  const { initializeNwmdData, loadLocations, loadTimeseries, loadLocationMetrics } = useNwmdData();
  const { selectLocation, selectedLocation } = useNwmdLocationSelection();
  const { mapFilters, updateMapFilters, timeseriesFilters, updateTimeseriesFilters } = useNwmdFilters();

  const handleViewportBoundsChange = useCallback((bounds) => {
    dispatch({
      type: ActionTypes.SET_MAP_VIEWPORT_BOUNDS,
      payload: bounds
    });
  }, [dispatch]);
  
  // Load initial data when component mounts
  useEffect(() => {
    const initializeData = async () => {
      try {
        await initializeNwmdData();
      } catch (error) {
        console.error('Nwmd Dashboard: Error during initialization:', error);
      }
    };
    
    initializeData();
  }, [initializeNwmdData]);
  
  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)', minHeight: 0 }}>
      {/* Height adjusted for navbar (Bootstrap navbar is typically 56px) */}
      
      <div className="container-fluid flex-grow-1 p-0" style={{ minHeight: 0, overflow: 'hidden' }}>
        <div 
          className="dashboard-grid h-100" 
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 2fr 2fr',
            gridTemplateRows: 'auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.8fr)',
            gap: '12px',
            padding: '12px',
            height: '100%',
            minHeight: 0,
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

          <div style={{
            gridColumn: '1 / 2',
            gridRow: state.error ? '2 / 4' : '1 / 4'
          }}>
            <FilterSidebar 
              state={state} 
              mapFilters={mapFilters}
              updateMapFilters={updateMapFilters}
              loadLocations={loadLocations} 
            />
          </div>
          
          {/* Map Panel - Left Column, reduced height */}
          <div 
            className="map-panel" 
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '2 / 4' : '1 / 4', // Reduced from 5 to 4
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              position: 'relative',
              minHeight: 0
            }}
          >
            <NwmdMapComponent
              state={state}
              dispatch={dispatch}
              ActionTypes={ActionTypes}
              selectLocation={selectLocation}
              loadLocations={loadLocations}
              getMetricLabel={getMetricLabel}
              onViewportBoundsChange={handleViewportBoundsChange}
            />
          </div>

          {/* CDF Plots - Right Column */}
          <div 
            className="cdf-plots-panel" 
            style={{
              gridColumn: '3 / 4',
              gridRow: state.error ? '2 / 4' : '1 / 4', // Keep same positioning
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              minHeight: 0
            }}
          >
              <div className="p-2 h-100 d-flex flex-column">
                <div style={{ flex: 1, minHeight: 0 }}>
                  <CdfPlot plotId="plot1" />
                </div>
              </div>
            {/* )} */}
          </div>

          {/* Location Info Card - Upper Right */}
          {/* <div 
            style={{
              gridColumn: '3 / 4',
              gridRow: state.error ? '2 / 3' : '1 / 2',
              minHeight: 0
            }}
          >
            <LocationCard 
              selectedLocation={state.selectedLocation}
              onClose={() => selectLocation(null)}
            />
          </div> */}

          {/* Timeseries Panel - Middle Right */}
          {/* <div 
            className="timeseries-panel" 
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '3 / 4' : '2 / 4', // Keep same positioning
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              minHeight: 0
            }}
          >
            {state.selectedLocation ? (
              <TimeseriesComponent
                state={state}
                TimeseriesControls={NwmdTimeseriesFilters}
                timeseriesControlsProps={{
                  state,
                  timeseriesFilters,
                  updateTimeseriesFilters,
                  loadTimeseries,
                  selectedLocation
                }}
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
          </div> */}

          {/* Metrics Panel - Bottom, right of filter sidebar */}
          <div 
            className="metrics-panel" 
            style={{
              gridColumn: '2 / -1', // Right of filter sidebar
              gridRow: state.error ? '5 / 6' : '4 / 5', // Bottom row
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden' // Prevent the panel itself from overflowing
            }}
          >
            {state.selectedLocation ? (
              <LocationMetrics
                selectedLocation={state.selectedLocation}
                locationMetrics={state.locationMetrics}
                metricsLoading={state.metricsLoading}
                error={state.error}
                loadLocationMetrics={loadLocationMetrics}
                tableProperties={state.tableProperties}
                defaultTable="nwmd_metrics_by_location"
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