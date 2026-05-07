import { useEffect, useCallback, useState } from 'react';
import { useDataDashboard, ActionTypes } from '../../../context/DataDashboardContext.jsx';
import { useDataDashboardData } from './useDataDashboardData';
import { MapComponent } from '../../common/dashboard';
import { LocationCard } from '../../common';
import ConfigurationsPanel from './ConfigurationsPanel';
import CompletenessHeatmap from './CompletenessHeatmap';
import { apiService } from '../../../services/api';

const Dashboard = () => {
  const { state, dispatch } = useDataDashboard();
  const { loadConfigurations, selectLocation } = useDataDashboardData();
  const [selectedCfg, setSelectedCfg] = useState(null);
  const [committedCfg, setCommittedCfg] = useState(null);
  const [huc8Locations, setHuc8Locations] = useState(null);

  // Load configurations and huc8 overlay locations on mount
  useEffect(() => {
    const initialize = async () => {
      try {
        await loadConfigurations();
      } catch (error) {
        console.error('Dashboard: Error during initialization:', error);
      }
    };
    initialize();
  }, [loadConfigurations]);

  useEffect(() => {
    apiService.getLocationsByPrefix('huc8')
      .then((data) => setHuc8Locations(data))
      .catch((err) => console.error('Dashboard: Failed to load huc8 locations:', err));
  }, []);

  const handleConfigurationSelect = useCallback((cfg) => {
    setSelectedCfg(cfg);
    if (!cfg || !Array.isArray(cfg.coordinates) || cfg.coordinates.length === 0) {
      dispatch({ type: ActionTypes.SET_LOCATIONS, payload: { type: 'FeatureCollection', features: [] } });
      return;
    }
    const features = cfg.coordinates
      .filter(([lon, lat]) => lon != null && lat != null)
      .map(([lon, lat]) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [lon, lat] },
        properties: { configuration_name: cfg.configuration_name }
      }));
    dispatch({
      type: ActionTypes.SET_LOCATIONS,
      payload: { type: 'FeatureCollection', features }
    });
  }, [dispatch, ActionTypes]);

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
            overflow: 'auto',
            gridAutoRows: '1fr'
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

          {/* Side-by-side: Map (left) + Configurations Panel (right) */}
          <div
            style={{
              gridColumn: '1 / -1',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '12px',
              height: '50vh',
              overflow: 'hidden'
            }}
          >
            {/* Map Panel - Left */}
            <div
              className="map-panel"
              style={{
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                overflow: 'hidden',
                position: 'relative',
                height: '50vh',
                flexShrink: 0
              }}
            >
              <MapComponent
                state={state}
                dispatch={dispatch}
                ActionTypes={ActionTypes}
                selectLocation={selectLocation}
                loadLocations={null}
                MapFilterButton={null}
                getMetricLabel={() => ''}
                showSearch={false}
                overlayLocations={huc8Locations}
              />
            </div>

            {/* Configurations Panel - Right */}
            <div
              style={{
                border: '1px solid #e0e0e0',
                borderRadius: '8px',
                overflow: 'hidden'
              }}
            >
              <ConfigurationsPanel
                configurations={state.configurations}
                loading={state.configsLoading}
                error={state.configurations.length === 0 && !state.configsLoading ? state.error : null}
                onSelect={handleConfigurationSelect}
                canGenerate={!!selectedCfg}
                onGenerate={() => setCommittedCfg(selectedCfg)}
              />
            </div>
          </div>

          {/* Heatmap Panel */}
          <div
            style={{
              gridColumn: '1 / -1',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              overflow: 'visible',
            }}
          >
            <CompletenessHeatmap
              configurationName={committedCfg?.configuration_name}
              variableName={committedCfg?.variable_name}
              unitName={committedCfg?.unit_name}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
