import { useEffect } from 'react';

import DashboardPanel from '@/shared/components/DashboardPanel';

import GriddedControls from './components/GriddedControls';
import GriddedMapComponent from './components/GriddedMapComponent';
import GriddedPolygonPanel from './components/GriddedPolygonPanel';
import GriddedTimeseriesPanel from './components/GriddedTimeseriesPanel';
import { useDashboard, ActionTypes } from './DashboardContext';
import { useGriddedVariableStyles } from './hooks/useGriddedVariableStyles';

export type GriddedTabName = 'dataset' | 'polygons';

const TABS: { id: GriddedTabName; label: string }[] = [
  { id: 'dataset', label: 'Dataset' },
  { id: 'polygons', label: 'Polygon Attributes' },
];

export const Dashboard = () => {
  const { state, dispatch } = useDashboard();
  const { resetStyles, applyVariableStyleIfNew } = useGriddedVariableStyles();

  // Reset style-tracking when dataset changes
  useEffect(() => {
    if (state.mapFilters.dataset) {
      resetStyles();
    }
  }, [state.mapFilters.dataset, resetStyles]);

  // Auto-apply variable-specific default styles on first selection of each variable
  useEffect(() => {
    applyVariableStyleIfNew(state.mapFilters.variable);
  }, [state.mapFilters.variable, applyVariableStyleIfNew]);

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100dvh - 56px)', minHeight: 0 }}>
      <div className="container-fluid flex-grow-1 p-0" style={{ minHeight: 0, overflow: 'hidden' }}>
        <div
          className="dashboard-grid h-100"
          style={{
            display: 'grid',
            gridTemplateColumns: '13fr 7fr',
            gridTemplateRows: 'auto minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1.1fr)',
            gap: '12px',
            padding: '12px',
            height: '100%',
            minHeight: 0,
            overflow: 'hidden',
          }}
        >
          {/* Error banner */}
          {state.error && (
            <div
              className="alert alert-danger alert-dismissible"
              role="alert"
              style={{ gridColumn: '1 / -1', gridRow: '1 / 2', zIndex: 1000, margin: 0 }}
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

          {/* Map panel — left */}
          <div
            className="map-panel"
            style={{
              gridColumn: '1 / 2',
              gridRow: state.error ? '2 / 4' : '1 / 4',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden',
              position: 'relative',
              minHeight: 0,
            }}
          >
            <GriddedMapComponent />
          </div>

          {/* Tabbed panel — right. Both tabs stay mounted and are hidden with
              display:none so their state survives switching. */}
          <div
            className="d-flex flex-column"
            style={{
              gridColumn: '2 / 3',
              gridRow: state.error ? '2 / 4' : '1 / 4',
              minHeight: 0,
            }}
          >
            <ul className="nav nav-tabs" style={{ flex: '0 0 auto' }}>
              {TABS.map((tab) => (
                <li className="nav-item" key={tab.id}>
                  <button
                    type="button"
                    className={`nav-link${state.rightPanelTab === tab.id ? ' active' : ''}`}
                    onClick={() =>
                      dispatch({ type: ActionTypes.SET_RIGHT_PANEL_TAB, payload: tab.id })
                    }
                    style={{ fontSize: '0.88rem', padding: '6px 16px' }}
                  >
                    {tab.label}
                  </button>
                </li>
              ))}
            </ul>

            <div style={{ flex: '1 1 0', minHeight: 0, position: 'relative' }}>
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: state.rightPanelTab === 'dataset' ? 'flex' : 'none',
                  flexDirection: 'column',
                }}
              >
                <DashboardPanel style={{ height: '100%' }} bodyStyle={{ overflow: 'auto' }}>
                  <GriddedControls />
                </DashboardPanel>
              </div>

              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: state.rightPanelTab === 'polygons' ? 'flex' : 'none',
                  flexDirection: 'column',
                }}
              >
                <GriddedPolygonPanel />
              </div>
            </div>
          </div>

          {/* Bottom full-width panel — timeseries plot for whichever query ran last */}
          <div
            style={{
              gridColumn: '1 / -1',
              gridRow: '4 / 5',
              minHeight: 0,
            }}
          >
            <GriddedTimeseriesPanel />
          </div>
        </div>
      </div>
    </div>
  );
};
