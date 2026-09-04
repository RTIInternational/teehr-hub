import { useCallback } from 'react';
import { Card } from 'react-bootstrap';
import Tab from 'react-bootstrap/Tab';
import Tabs from 'react-bootstrap/Tabs';

import { CdfPlot } from './components/CdfPlot';
import { CdfSidebar } from './components/CdfSidebar';
import { FilterSidebar } from './components/FilterSidebar';
import LeadTimeBinPlot from './components/LeadTimeBinPlot';
import NwmdMapComponent from './components/NwmdMapComponent';
import { SiteInfo } from './components/SiteInfo';
import TimeseriesNoControls from './components/TimeseriesNoControls';
import { useDashboard, ActionTypes } from './DashboardContext';
import { useFilters } from './hooks/useFilters';
import { useInitialFilters } from './hooks/useInitialFilters';
import { useLocationSelection } from './hooks/useLocationSelection';
import type { ViewportBounds } from './types/maps';

export const Dashboard = () => {
  const tables = ['nwmd_metrics_by_location'];

  useInitialFilters(tables[0]);

  const { state, dispatch } = useDashboard();
  const { selectLocation, selectedLocation } = useLocationSelection();
  const { mapFilters, timeseriesFilters } = useFilters();
  const hasSelectedLocation = Boolean(state.selectedLocation?.primary_location_id);

  const handleViewportBoundsChange = useCallback(
    (bounds: ViewportBounds) => {
      dispatch({
        type: ActionTypes.SET_MAP_VIEWPORT_BOUNDS,
        payload: bounds,
      });
    },
    [dispatch]
  );

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)', minHeight: 0 }}>
      {/* Height adjusted for navbar (Bootstrap navbar is typically 56px) */}
      <div className="container-fluid flex-grow-1 p-0" style={{ minHeight: 0, overflow: 'hidden' }}>
        <div
          className="dashboard-grid h-100"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 2fr 2fr',
            gridTemplateRows: 'auto minmax(0, 1.5fr) minmax(0, 1fr)',
            gap: '12px',
            padding: '12px',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
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
                margin: 0,
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

          <div
            className="nwmd-filter-tabs"
            style={{
              gridColumn: '1 / 2',
              gridRow: '2 / 3',
              minHeight: 0,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <Tabs defaultActiveKey="filter" id="cdf-tabs">
              <Tab eventKey="filter" title="Filters" className="overflow-y-auto">
                <FilterSidebar tables={tables} />
              </Tab>
              <Tab eventKey="cdf" title="CDF Config">
                <CdfSidebar tables={tables} />
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
              minHeight: 0,
            }}
          >
            <NwmdMapComponent
              state={state}
              dispatch={dispatch}
              table={tables[0]}
              ActionTypes={ActionTypes}
              selectLocation={selectLocation}
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
              minHeight: 0,
            }}
          >
            <div
              className="p-2 h-100"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gridTemplateRows: '1fr 1fr',
                gap: '5px',
              }}
            >
              <CdfPlot table={tables[0]} plotId="Metric 1" />
              <CdfPlot table={tables[0]} plotId="Metric 2" />
              <CdfPlot table={tables[0]} plotId="Metric 3" />
              <CdfPlot table={tables[0]} plotId="Metric 4" />
            </div>
            {/* )} */}
          </div>

          <div
            style={{
              gridColumn: '1 / -1',
              gridRow: '3 / -1',
              minHeight: 0,
              display: 'grid',
              gridTemplateColumns: '1fr 2fr 1fr',
              gap: '12px',
            }}
          >
            {!hasSelectedLocation ? (
              <Card
                className="shadow-lg h-100 d-flex flex-column"
                style={{ borderRadius: '8px', gridColumn: '1 / -1' }}
              >
                <Card.Body className="d-flex align-items-center justify-content-center text-muted">
                  <div className="text-center">
                    <div style={{ fontSize: '3rem' }}>📍</div>
                    <h5>Select a Location</h5>
                    <p className="mb-0">
                      Click on a location on the map to load site info and charts.
                    </p>
                  </div>
                </Card.Body>
              </Card>
            ) : (
              <>
                <div style={{ minHeight: 0 }}>
                  <SiteInfo selectedLocation={state.selectedLocation} />
                </div>
                <div
                  className="timeseries-panel"
                  style={{
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    minHeight: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden', // Prevent the panel itself from overflowing
                  }}
                >
                  <TimeseriesNoControls
                    selectedLocation={selectedLocation}
                    timeseriesFilters={timeseriesFilters}
                  />
                </div>
                <div
                  style={{
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    minHeight: 0,
                    overflow: 'hidden',
                  }}
                >
                  <LeadTimeBinPlot
                    table={tables[0]}
                    selectedLocation={state.selectedLocation}
                    mapFilters={mapFilters}
                  />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
