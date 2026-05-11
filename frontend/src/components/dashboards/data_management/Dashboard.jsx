import { useEffect, useCallback, useState } from 'react';
import { useDataDashboard, ActionTypes } from '../../../context/DataDashboardContext.jsx';
import { useDataDashboardData } from './useDataDashboardData';
import { MapComponent } from '../../common/dashboard';
import { LocationCard } from '../../common';
import ConfigurationsPanel from './ConfigurationsPanel';
import CompletenessHeatmap from './CompletenessHeatmap';
import AttributesPanel from './AttributesPanel';
import { apiService } from '../../../services/api';

const Dashboard = () => {
  const { state, dispatch } = useDataDashboard();
  const { loadConfigurations, selectLocation } = useDataDashboardData();
  const [selectedCfg, setSelectedCfg] = useState(null);
  const [committedCfg, setCommittedCfg] = useState(null);
  const [completenessGeometries, setCompletenessGeometries] = useState(null);
  const [hoveredSpatialAggregate, setHoveredSpatialAggregate] = useState(null);
  const [overlayVisible, setOverlayVisible] = useState(false);

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

  // Load spatial aggregate geometries when a configuration is committed
  useEffect(() => {
    if (!committedCfg) {
      setCompletenessGeometries(null);
      return;
    }
    apiService.getCompletenessGeometries({
      configuration_name: committedCfg.configuration_name,
      variable_name: committedCfg.variable_name,
    })
      .then((data) => setCompletenessGeometries(data))
      .catch((err) => console.error('Dashboard: Failed to load completeness geometries:', err));
  }, [committedCfg]);

  const handleConfigurationSelect = useCallback((cfg) => {
    setSelectedCfg(cfg);
    setCommittedCfg(null);
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
    <div
      className="d-flex flex-column"
      style={{ height: 'calc(100vh - 56px)', overflow: 'hidden', padding: '12px', gap: '12px' }}
    >
      {/* Error Alert */}
      {state.error && (
        <div
          className="alert alert-danger alert-dismissible"
          role="alert"
          style={{ flex: '0 0 auto', margin: 0, zIndex: 1000 }}
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

      {/* Top half: Map (left) + Configurations Panel (right) */}
      <div
        style={{
          flex: '1 1 0',
          minHeight: 0,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
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
            overlayLocations={completenessGeometries}
            overlayVisible={overlayVisible}
            hoveredOverlayId={hoveredSpatialAggregate ?? null}
          />
          {/* HUC8 layer toggle */}
          <button
            className={`btn btn-sm position-absolute ${overlayVisible ? 'btn-primary' : 'btn-outline-secondary bg-white'}`}
            style={{ bottom: '10px', left: '10px', zIndex: 1100, fontSize: '0.7rem', padding: '2px 8px', opacity: 0.9 }}
            onClick={() => setOverlayVisible((v) => !v)}
            title="Toggle spatial aggregate boundaries"
          >
            Boundaries {overlayVisible ? 'On' : 'Off'}
          </button>
        </div>

        {/* Configurations Panel - Right */}
        <div
          style={{
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          <ConfigurationsPanel
            configurations={state.configurations}
            loading={state.configsLoading}
            error={state.configurations.length === 0 && !state.configsLoading ? state.error : null}
            onSelect={handleConfigurationSelect}
            canGenerate={!!selectedCfg}
            onGenerate={() => { setCommittedCfg(selectedCfg); setOverlayVisible(true); }}
          />
        </div>
      </div>

      {/* Bottom half: Heatmap (left) + Attributes Panel (right) */}
      <div
        style={{
          flex: '1 1 0',
          minHeight: 0,
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '12px',
        }}
      >
        {/* Completeness Heatmap - Bottom Left */}
        <div
          style={{
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          <CompletenessHeatmap
            configurationName={committedCfg?.configuration_name}
            variableName={committedCfg?.variable_name}
            onHover={setHoveredSpatialAggregate}
          />
        </div>

        {/* Attributes Panel - Bottom Right */}
        <div
          style={{
            border: '1px solid #e0e0e0',
            borderRadius: '8px',
            overflow: 'hidden',
          }}
        >
          <AttributesPanel />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
