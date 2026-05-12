/**
 * CompletenessTab
 *
 * Layout:  selector bar (top) | map (left half) + heatmap (right half)
 *
 * Behaviour
 * ---------
 * - Loads available configurations from configurations_summary for the dropdowns.
 * - "Generate" fetches overlay polygon geometries and passes them to the map,
 *   and passes configuration_name / variable_name to the heatmap.
 * - Heatmap hover updates hoveredSpatialAggregate → highlights the matching
 *   polygon on the map.
 * - Boundaries toggle shows/hides the overlay layer.
 */
import { useState, useCallback, useEffect } from 'react';
import { Form } from 'react-bootstrap';
import SimpleMapPanel from './SimpleMapPanel';
import CompletenessHeatmap from './CompletenessHeatmap';
import { apiService } from '../../../services/api';

const CONFIG_OPTIONS = ['usgs_observations'];
const VARIABLE_OPTIONS = ['streamflow_hourly_inst'];

// ── Component ──────────────────────────────────────────────────────────────
const CompletenessTab = ({ isActive = true }) => {
  const [selectedCfg, setSelectedCfg]   = useState('');
  const [selectedVar, setSelectedVar]   = useState('');

  // "Committed" state: set when Generate is clicked
  const [committedCfg, setCommittedCfg] = useState(null);

  // Map overlay state
  const [overlayGeometries, setOverlayGeometries]             = useState(null);
  const [overlayVisible, setOverlayVisible]                   = useState(true);
  const [hoveredSpatialAggregate, setHoveredSpatialAggregate] = useState(null);

  const canGenerate = !!selectedCfg && !!selectedVar;

  // Load overlay geometries when committed configuration changes
  useEffect(() => {
    if (!committedCfg) {
      setOverlayGeometries(null);
      return;
    }
    apiService
      .getCompletenessGeometries({
        configuration_name: committedCfg.configuration_name,
        variable_name: committedCfg.variable_name,
      })
      .then((data) => setOverlayGeometries(data))
      .catch((err) => console.error('CompletenessTab: Failed to load overlay geometries:', err));
  }, [committedCfg]);

  const handleGenerate = useCallback(() => {
    if (!canGenerate) return;
    setCommittedCfg({ configuration_name: selectedCfg, variable_name: selectedVar });
    setOverlayVisible(true);
  }, [canGenerate, selectedCfg, selectedVar]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Selector bar */}
      <div
        className="d-flex align-items-center gap-2 px-3 py-2 border-bottom"
        style={{ flex: '0 0 auto', background: '#f8f9fa' }}
      >
        <Form.Select
          size="sm"
          value={selectedCfg}
          onChange={(e) => { setSelectedCfg(e.target.value); setSelectedVar(''); setCommittedCfg(null); setOverlayGeometries(null); }}
          aria-label="Select configuration"
          style={{ maxWidth: 280 }}
        >
          <option value="">— Select a configuration —</option>
          {CONFIG_OPTIONS.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>

        <Form.Select
          size="sm"
          value={selectedVar}
          onChange={(e) => setSelectedVar(e.target.value)}
          aria-label="Select variable"
          disabled={!selectedCfg}
          style={{ maxWidth: 240 }}
        >
          <option value="">— Select a variable —</option>
          {VARIABLE_OPTIONS.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>

        <button
          className="btn btn-primary btn-sm"
          disabled={!canGenerate}
          onClick={handleGenerate}
        >
          Generate
        </button>
      </div>

      {/* Map + Heatmap side-by-side */}
      <div style={{ flex: '1 1 0', minHeight: 0, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>

        {/* Map */}
        <div style={{ borderRight: '1px solid #dee2e6', position: 'relative' }}>
          <SimpleMapPanel
            overlayLocations={overlayGeometries}
            overlayVisible={overlayVisible}
            hoveredOverlayId={hoveredSpatialAggregate}
            showOverlayToggle={!!overlayGeometries}
            onOverlayToggle={() => setOverlayVisible((v) => !v)}
            isActive={isActive}
          />
        </div>

        {/* Heatmap */}
        <div style={{ overflow: 'hidden' }}>
          <CompletenessHeatmap
            configurationName={committedCfg?.configuration_name}
            variableName={committedCfg?.variable_name}
            onHover={setHoveredSpatialAggregate}
          />
        </div>
      </div>
    </div>
  );
};

export default CompletenessTab;
