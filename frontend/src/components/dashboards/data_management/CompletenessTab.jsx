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
import { useEffect, useState, useCallback } from 'react';
import { Spinner, Form } from 'react-bootstrap';
import SimpleMapPanel from './SimpleMapPanel';
import CompletenessHeatmap from './CompletenessHeatmap';
import { apiService } from '../../../services/api';

// ── Component ──────────────────────────────────────────────────────────────
const CompletenessTab = ({ isActive = true }) => {
  // Config/variable dropdowns
  const [configRows, setConfigRows]         = useState([]);
  const [configsLoading, setConfigsLoading] = useState(false);
  const [selectedCfg, setSelectedCfg]       = useState('');
  const [selectedVar, setSelectedVar]       = useState('');

  // "Committed" state: set when Generate is clicked
  const [committedCfg, setCommittedCfg]     = useState(null);  // { configuration_name, variable_name }

  // Map overlay state
  const [overlayGeometries, setOverlayGeometries] = useState(null);
  const [overlayVisible, setOverlayVisible]         = useState(true);
  const [hoveredSpatialAggregate, setHoveredSpatialAggregate] = useState(null);

  // Load configurations list for dropdowns on mount
  useEffect(() => {
    let cancelled = false;
    setConfigsLoading(true);

    apiService.getConfigurationsTable()
      .then((data) => {
        if (cancelled) return;
        const items = Array.isArray(data)
          ? data
          : Array.isArray(data.items) ? data.items : (data.features || []).map((f) => f.properties ?? f);
        setConfigRows(items);
      })
      .catch((err) => console.error('CompletenessTab: Failed to load configs:', err))
      .finally(() => { if (!cancelled) setConfigsLoading(false); });

    return () => { cancelled = true; };
  }, []);

  // Unique configuration names
  const configNames = [...new Set(configRows.map((r) => r.configuration_name))].sort();

  // Variable names for the selected config
  const variableNames = selectedCfg
    ? [...new Set(
        configRows
          .filter((r) => r.configuration_name === selectedCfg)
          .map((r) => r.variable_name)
      )].sort()
    : [];

  const canGenerate = !!selectedCfg && !!selectedVar;

  // When config selection changes, reset variable + committed state
  const handleCfgChange = (val) => {
    setSelectedCfg(val);
    setSelectedVar('');
    setCommittedCfg(null);
    setOverlayGeometries(null);
  };

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
        {configsLoading ? (
          <Spinner animation="border" size="sm" variant="secondary" />
        ) : (
          <>
            <Form.Select
              size="sm"
              value={selectedCfg}
              onChange={(e) => handleCfgChange(e.target.value)}
              aria-label="Select configuration"
              style={{ maxWidth: 280 }}
            >
              <option value="">— Select a configuration —</option>
              {configNames.map((name) => (
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
              {variableNames.map((name) => (
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
          </>
        )}
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
