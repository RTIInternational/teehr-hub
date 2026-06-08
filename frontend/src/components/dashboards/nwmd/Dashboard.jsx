import { useCallback, useEffect } from 'react';
import { useNwmdDashboard, ActionTypes } from '../../../context/NwmdDashboardContext.jsx';
import { useNwmdLocationSelection, useNwmdFilters } from '../../../hooks/useNwmdDataFetching';
import { LocationCard } from '../../common';
import { getMetricLabel } from '../../common/dashboard/utils.js';
import { useNwmdData } from './useNwmdData';
import { NwmdMapComponent } from './NwmdMapComponent.jsx'
import { FilterSidebar } from './FilterSidebar.jsx';
import { CdfPlot } from './CdfPlot.jsx';
import { useCdfPlots } from './useCdfPlots.js';
import { CdfSidebar } from './CdfSidebar.jsx';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';
import TimeseriesNoControls from './TimeseriesNoControls.jsx';

const Dashboard = () => {
  const { state, dispatch } = useNwmdDashboard();
  const { initializeNwmdData, loadLocations, loadTimeseries, loadLocationMetrics } = useNwmdData();
  const { selectLocation, selectedLocation } = useNwmdLocationSelection();
  const { mapFilters, updateMapFilters, timeseriesFilters, updateTimeseriesFilters } = useNwmdFilters();
  const { plotIds, setCdfPlotMetric } = useCdfPlots();

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
            gridTemplateRows: 'auto minmax(0, 1.5fr) auto minmax(0, 1fr)',
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
            gridRow: '2 / -1'
          }}>
            <Tabs
              defaultActiveKey="filter"
              id="cdf-tabs"
              className="mb-3"
            >
              <Tab eventKey="filter" title="Filters">
                <FilterSidebar 
                  state={state} 
                  mapFilters={mapFilters}
                  updateMapFilters={updateMapFilters}
                  loadLocations={loadLocations} 
                />
              </Tab>
              <Tab eventKey="cdf" title="CDF Config">
                <CdfSidebar
                  state={state}
                  plotIds={plotIds}
                  setCdfPlotMetric={setCdfPlotMetric}
                />
              </Tab>
            </Tabs>
          </div>
          
          {/* Map Panel - Left Column, reduced height */}
          <div 
            className="map-panel" 
            style={{
              gridColumn: '2 / 3',
              gridRow: '2 / 3',
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
              gridRow: '2 / 3',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              minHeight: 0
            }}
          >
              <div 
                className="p-2 h-100"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gridTemplateRows: '1fr 1fr',
                  gap: '5px'
                }}
              >
                <CdfPlot plotId="Metric 1" />
                <CdfPlot plotId="Metric 2" />
                <CdfPlot plotId="Metric 3" />
                <CdfPlot plotId="Metric 4" />
              </div>
            {/* )} */}
          </div>

          {/* Location Info Card - Upper Right */}
          <div 
            style={{
              gridColumn: '2 / -1',
              gridRow: '3 / 4',
              minHeight: 0
            }}
          >
            <LocationCard 
              selectedLocation={state.selectedLocation}
              onClose={() => selectLocation(null)}
            />
          </div>

          {/* Timeseries Panel - Bottom, right of filter sidebar */}
          <div 
            className="timeseries-panel" 
            style={{
              gridColumn: '2 / -1',
              gridRow: '4 / -1',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden' // Prevent the panel itself from overflowing
            }}
          >
            <TimeseriesNoControls 
              selectedLocation={selectedLocation}
              timeseriesFilters={timeseriesFilters}
              timeseriesData={state.timeseriesData}
              timeseriesLoading={state.timeseriesLoading}
              loadTimeseries={loadTimeseries}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;