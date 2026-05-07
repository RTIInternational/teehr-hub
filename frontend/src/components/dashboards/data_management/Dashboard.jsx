import { useEffect } from 'react';
import { useDataDashboard, ActionTypes } from '../../../context/DataDashboardContext.jsx';
import { useDataDashboardData } from './useDataDashboardData';
import { MapComponent } from '../../common/dashboard';
import { LocationCard } from '../../common';
import ConfigurationsPanel from './ConfigurationsPanel';

const Dashboard = () => {
  const { state, dispatch } = useDataDashboard();
  const { initializeDataDashboard, loadLocations, selectLocation } = useDataDashboardData();

  // Load initial data on mount
  useEffect(() => {
    const initialize = async () => {
      try {
        await initializeDataDashboard();
      } catch (error) {
        console.error('Dashboard: Error during initialization:', error);
      }
    };
    initialize();
  }, [initializeDataDashboard]);

  return (
    <div className="d-flex flex-column" style={{ height: 'calc(100vh - 56px)' }}>
      <div className="container-fluid flex-grow-1 p-0">
        <div
          className="dashboard-grid h-100"
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr',
            gridTemplateRows: 'auto 1fr',
            gap: '12px',
            padding: '12px',
            height: '100%',
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

          {/* Configurations Panel - Top */}
          <div
            style={{
              gridColumn: '1 / -1',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'hidden'
            }}
          >
            <ConfigurationsPanel
              configurations={state.configurations}
              loading={state.configsLoading}
              error={state.configurations.length === 0 && !state.configsLoading ? state.error : null}
            />
          </div>

          {/* Map Panel - Below */}
          <div
            className="map-panel"
            style={{
              gridColumn: '1 / -1',
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
              MapFilterButton={null}
              getMetricLabel={() => ''}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
