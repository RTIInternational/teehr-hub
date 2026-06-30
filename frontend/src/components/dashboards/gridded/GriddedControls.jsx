import { useState } from 'react';
import { Form, Row, Col, Button, InputGroup } from 'react-bootstrap';
import { useGriddedDashboard, ActionTypes } from '../../../context/GriddedDashboardContext.jsx';
import { OVERLAY_LAYERS } from './overlayLayers.js';

const COLOR_RAMPS = [
  { label: 'Plasma', value: 'raster/plasma' },
  { label: 'Viridis', value: 'raster/viridis' },
  { label: 'Inferno', value: 'raster/inferno' },
  { label: 'Blues', value: 'raster/Blues' },
  { label: 'RdBu', value: 'raster/RdBu' },
];

const GriddedControls = ({ loadVariables, loadTimesteps }) => {
  const [overlaysExpanded, setOverlaysExpanded] = useState(true);
  const { state, dispatch } = useGriddedDashboard();
  const { datasets, variables, timesteps, mapFilters, activeOverlays } = state;
  const { dataset, variable, timestepIndex, colorRamp, colorRampMin, colorRampMax } = mapFilters;

  const currentTimestep = timesteps[timestepIndex] ?? '';
  const canStepBack = timestepIndex > 0;
  const canStepForward = timestepIndex < timesteps.length - 1;

  const handleDatasetChange = async (e) => {
    const selected = e.target.value || null;
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { dataset: selected, timestepIndex: 0 } });
    if (selected) {
      await loadVariables(selected);
    }
  };

  const handleVariableChange = async (e) => {
    const selected = e.target.value || null;
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { variable: selected, timestepIndex: 0 } });
    if (dataset && selected) {
      await loadTimesteps(dataset, selected);
    }
  };

  const handlePrevTimestep = () => {
    if (canStepBack) {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { timestepIndex: timestepIndex - 1 } });
    }
  };

  const handleNextTimestep = () => {
    if (canStepForward) {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { timestepIndex: timestepIndex + 1 } });
    }
  };

  const handleColorRampChange = (e) => {
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { colorRamp: e.target.value } });
  };

  const handleRangeChange = (field, value) => {
    const num = parseFloat(value);
    if (!Number.isNaN(num)) {
      dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { [field]: num } });
    }
  };

  return (
    <div className="h-100 d-flex flex-column overflow-auto p-1">
      <Form>
        <Row className="g-2">
          {/* Overlay layer toggles */}
          <Col md={12}>
            <button
              type="button"
              className="small fw-bold btn btn-link p-0 text-decoration-none text-reset d-flex align-items-center gap-1"
              onClick={() => setOverlaysExpanded((v) => !v)}
              aria-expanded={overlaysExpanded}
            >
              <span style={{ fontSize: '0.65rem' }}>{overlaysExpanded ? '▼' : '▶'}</span>
              <span>Overlay Layers</span>
            </button>
            {overlaysExpanded && (
              <div className="mt-1">
                {OVERLAY_LAYERS.map((overlay) => (
                  <Form.Check
                    key={overlay.id}
                    type="checkbox"
                    id={`overlay-${overlay.id}`}
                    label={<span style={{ fontSize: '0.8rem' }}>{overlay.label}</span>}
                    checked={activeOverlays.includes(overlay.id)}
                    onChange={() => dispatch({ type: ActionTypes.TOGGLE_OVERLAY, payload: overlay.id })}
                    className="mb-1"
                  />
                ))}
              </div>
            )}
          </Col>

          {/* Dataset selector */}
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Dataset</Form.Label>
              <Form.Select
                size="sm"
                value={dataset ?? ''}
                onChange={handleDatasetChange}
                disabled={datasets.length === 0}
              >
                <option value="">Select dataset…</option>
                {datasets.map((ds) => (
                  <option key={ds} value={ds}>{ds}</option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>

          {/* Variable selector */}
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Variable</Form.Label>
              <Form.Select
                size="sm"
                value={variable ?? ''}
                onChange={handleVariableChange}
                disabled={!dataset || variables.length === 0}
              >
                <option value="">Select variable…</option>
                {variables.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>

          {/* Timestep pager */}
          <Col md={12}>
            <Form.Label className="small fw-bold d-block">Time Step</Form.Label>
            <InputGroup size="sm">
              <Button
                variant="outline-secondary"
                onClick={handlePrevTimestep}
                disabled={!canStepBack}
                title="Previous time step"
              >
                &#9664;
              </Button>
              <Form.Control
                readOnly
                value={currentTimestep || (variable ? 'No timesteps available' : '—')}
                className="text-center"
                style={{ fontSize: '0.8rem' }}
              />
              <Button
                variant="outline-secondary"
                onClick={handleNextTimestep}
                disabled={!canStepForward}
                title="Next time step"
              >
                &#9654;
              </Button>
            </InputGroup>
            {timesteps.length > 0 && (
              <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                {timestepIndex + 1} / {timesteps.length}
              </div>
            )}
          </Col>

          {/* Color ramp */}
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Color Scale</Form.Label>
              <Form.Select
                size="sm"
                value={colorRamp}
                onChange={handleColorRampChange}
              >
                {COLOR_RAMPS.map((cr) => (
                  <option key={cr.value} value={cr.value}>{cr.label}</option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>

          {/* Color ramp range */}
          <Col md={6}>
            <Form.Group>
              <Form.Label className="small fw-bold">Min</Form.Label>
              <Form.Control
                size="sm"
                type="number"
                value={colorRampMin}
                onChange={(e) => handleRangeChange('colorRampMin', e.target.value)}
              />
            </Form.Group>
          </Col>
          <Col md={6}>
            <Form.Group>
              <Form.Label className="small fw-bold">Max</Form.Label>
              <Form.Control
                size="sm"
                type="number"
                value={colorRampMax}
                onChange={(e) => handleRangeChange('colorRampMax', e.target.value)}
              />
            </Form.Group>
          </Col>
        </Row>
      </Form>
    </div>
  );
};

export default GriddedControls;
