import { useEffect, useState } from 'react';
import { Form, Row, Col, Button, InputGroup, Spinner, Alert } from 'react-bootstrap';

import { useDatasets } from '@/shared/queries/gridded/datasets';
import { usePolygonLayers } from '@/shared/queries/gridded/tiles';
import { useTimesteps } from '@/shared/queries/gridded/timesteps';
import { useVariableAttrs } from '@/shared/queries/gridded/variableAttrs';
import { useVariables } from '@/shared/queries/gridded/variables';
import { parseUtcTime, shortestStep } from '@/shared/utils/dates';

import { useDashboard, ActionTypes } from '../DashboardContext';
import { useCurrentTimestep } from '../hooks/useCurrentTimestep';
import { OVERLAY_LAYERS } from '../utils/overlayLayers';

const COLOR_RAMPS = [
  { label: 'Plasma', value: 'raster/plasma' },
  { label: 'Turbo', value: 'raster/turbo' },
  { label: 'Viridis', value: 'raster/viridis' },
  { label: 'Inferno', value: 'raster/inferno' },
  { label: 'Blues', value: 'raster/Blues' },
  { label: 'RdBu', value: 'raster/RdBu' },
];

const GriddedControls = () => {
  const [overlaysExpanded, setOverlaysExpanded] = useState(false);
  const [polygonLayersExpanded, setPolygonLayersExpanded] = useState(false);
  const [mapControlsExpanded, setMapControlsExpanded] = useState(false);
  const { state, dispatch } = useDashboard();
  const { mapFilters, activeOverlays, activePolygonLayer } = state;
  const { dataset, variable, timestepIndex, colorRamp, colorRampMin, colorRampMax } = mapFilters;

  const datasets = useDatasets();
  const variables = useVariables(dataset);
  const timesteps = useTimesteps(dataset);
  const variableAttrs = useVariableAttrs(dataset);

  const units = variable ? variableAttrs.data?.[variable]?.units : undefined;

  const currentTimestep = useCurrentTimestep() ?? '';
  const canStepBack = timestepIndex > 0;
  const canStepForward = timestepIndex < timesteps.data.length - 1;

  const polygonLayers = usePolygonLayers();

  // Auto-select variable when dataset is selected
  useEffect(() => {
    if (!dataset) return;
    if (variables.data.length === 0) return;

    const currentIsValid = !!variable && variables.data.includes(variable);
    if (currentIsValid) return;

    dispatch({
      type: ActionTypes.UPDATE_MAP_FILTERS,
      payload: { variable: variables.data[0], timestepIndex: 0 },
    });
  }, [dataset, variable, variables.data, dispatch]);

  // Daily or coarser data picks a date only; sub-daily data picks the hour too
  const isDaily = shortestStep(timesteps.data.map(parseUtcTime)) >= 24 * 60 * 60 * 1000;
  const pickerLength = isDaily ? 10 : 16;

  // Jump to the timestep nearest the picked date; times are naive UTC
  const selectTimestep = (value: string) => {
    if (!value || timesteps.data.length === 0) return;
    // A picked date takes the data's time of day, so steps at e.g. 23:00 match the same day
    const picked = parseUtcTime(isDaily ? value + currentTimestep.slice(10) : value);
    let closestIdx = 0;
    let closestDiff = Infinity;
    timesteps.data.forEach((ts, i) => {
      const diff = Math.abs(parseUtcTime(ts) - picked);
      if (diff < closestDiff) {
        closestDiff = diff;
        closestIdx = i;
      }
    });
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { timestepIndex: closestIdx } });
  };

  const handleDatasetChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value || null;
    dispatch({
      type: ActionTypes.UPDATE_MAP_FILTERS,
      payload: { dataset: selected, timestepIndex: 0 },
    });
  };

  const handleVariableChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selected = e.target.value || null;
    dispatch({
      type: ActionTypes.UPDATE_MAP_FILTERS,
      payload: { variable: selected, timestepIndex: 0 },
    });
  };

  const handlePrevTimestep = () => {
    if (canStepBack) {
      dispatch({
        type: ActionTypes.UPDATE_MAP_FILTERS,
        payload: { timestepIndex: timestepIndex - 1 },
      });
    }
  };

  const handleNextTimestep = () => {
    if (canStepForward) {
      dispatch({
        type: ActionTypes.UPDATE_MAP_FILTERS,
        payload: { timestepIndex: timestepIndex + 1 },
      });
    }
  };

  const handleColorRampChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { colorRamp: e.target.value } });
  };

  const handleRangeChange = (field: string, value: string) => {
    const num = parseFloat(value);
    if (Number.isNaN(num)) return;
    if (field === 'colorRampMin' && num >= colorRampMax) return;
    if (field === 'colorRampMax' && num <= colorRampMin) return;
    dispatch({ type: ActionTypes.UPDATE_MAP_FILTERS, payload: { [field]: num } });
  };

  return (
    <div className="h-100 d-flex flex-column overflow-auto p-1">
      <Form onSubmit={(e) => e.preventDefault()}>
        <Row className="g-2">
          {/* Dataset selector */}
          <Col md={12}>
            <Form.Group>
              <Form.Label className="small fw-bold">Dataset</Form.Label>
              <Form.Select
                size="sm"
                value={dataset ?? ''}
                onChange={handleDatasetChange}
                disabled={datasets.data.length === 0}
              >
                <option value="">Select dataset…</option>
                {datasets.data.map((ds) => (
                  <option key={ds} value={ds}>
                    {ds}
                  </option>
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
                disabled={!dataset || variables.data.length === 0}
              >
                <option value="">Select variable…</option>
                {variables.data.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </Col>

          {/* Timestep pager */}
          <Col md={12}>
            <Form.Label className="small fw-bold d-block">Time Step (UTC)</Form.Label>
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
                type={isDaily ? 'date' : 'datetime-local'}
                value={currentTimestep.slice(0, pickerLength)}
                min={timesteps.data[0]?.slice(0, pickerLength)}
                max={timesteps.data[timesteps.data.length - 1]?.slice(0, pickerLength)}
                onChange={(e) => selectTimestep(e.target.value)}
                disabled={timesteps.data.length === 0}
                className="text-center"
                style={{ fontSize: '0.8rem' }}
                title="Pick a date or use the arrows to step"
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
            {timesteps.data.length > 0 && (
              <div className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>
                {timestepIndex + 1} / {timesteps.data.length}
              </div>
            )}
          </Col>

          {/* Polygon layers (exclusive selection) */}
          <Col md={12}>
            <button
              type="button"
              className="small btn btn-link p-0 text-decoration-none d-flex align-items-center gap-1"
              style={{ color: '#555658', fontWeight: 700 }}
              onClick={() => setPolygonLayersExpanded((v) => !v)}
              aria-expanded={polygonLayersExpanded}
            >
              <span style={{ fontSize: '0.65rem' }}>{polygonLayersExpanded ? '▼' : '▶'}</span>
              <span>Polygon Layers</span>
            </button>
            {polygonLayersExpanded && (
              <div className="mt-1">
                {polygonLayers.isLoading && (
                  <div className="d-flex align-items-center gap-2">
                    <Spinner animation="border" size="sm" />
                    <span style={{ fontSize: '0.75rem' }}>Loading layers…</span>
                  </div>
                )}
                {polygonLayers.isError && (
                  <Alert
                    variant="warning"
                    className="py-1 px-2 mb-1"
                    style={{ fontSize: '0.8rem' }}
                  >
                    {polygonLayers.error.message}
                  </Alert>
                )}
                {!polygonLayers.isLoading &&
                  polygonLayers.data?.length === 0 &&
                  !polygonLayers.isError && (
                    <span style={{ fontSize: '0.75rem', color: '#6c757d' }}>
                      No polygon layers available
                    </span>
                  )}
                {!polygonLayers.isLoading &&
                  polygonLayers.data?.map((layer) => (
                    <Form.Check
                      key={layer.id}
                      type="checkbox"
                      id={`polygon-${layer.id}`}
                      label={<span style={{ fontSize: '0.8rem' }}>{layer.id}</span>}
                      checked={activePolygonLayer === layer.id}
                      onChange={() =>
                        dispatch({
                          type: ActionTypes.SET_ACTIVE_POLYGON_LAYER,
                          payload: activePolygonLayer === layer.id ? null : layer.id,
                        })
                      }
                      className="mb-1"
                    />
                  ))}
              </div>
            )}
          </Col>

          {/* Overlay layer toggles */}
          <Col md={12}>
            <button
              type="button"
              className="small btn btn-link p-0 text-decoration-none d-flex align-items-center gap-1"
              style={{ color: '#555658', fontWeight: 700 }}
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
                    onChange={() =>
                      dispatch({ type: ActionTypes.TOGGLE_OVERLAY, payload: overlay.id })
                    }
                    className="mb-1"
                  />
                ))}
              </div>
            )}
          </Col>

          {/* Map controls (color ramp + range) */}
          <Col md={12}>
            <button
              type="button"
              className="small btn btn-link p-0 text-decoration-none d-flex align-items-center gap-1"
              style={{ color: '#555658', fontWeight: 700 }}
              onClick={() => setMapControlsExpanded((v) => !v)}
              aria-expanded={mapControlsExpanded}
            >
              <span style={{ fontSize: '0.65rem' }}>{mapControlsExpanded ? '▼' : '▶'}</span>
              <span>Display Controls</span>
            </button>
            {mapControlsExpanded && (
              <Row className="g-2 mt-0">
                <Col md={12}>
                  <Form.Group>
                    <Form.Label className="small fw-bold">Color Scale</Form.Label>
                    <Form.Select size="sm" value={colorRamp} onChange={handleColorRampChange}>
                      {COLOR_RAMPS.map((cr) => (
                        <option key={cr.value} value={cr.value}>
                          {cr.label}
                        </option>
                      ))}
                    </Form.Select>
                  </Form.Group>
                </Col>
                <Col md={6}>
                  <Form.Group>
                    <Form.Label className="small fw-bold">
                      Min{units ? ` (${units})` : ''}
                    </Form.Label>
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
                    <Form.Label className="small fw-bold">
                      Max{units ? ` (${units})` : ''}
                    </Form.Label>
                    <Form.Control
                      size="sm"
                      type="number"
                      value={colorRampMax}
                      onChange={(e) => handleRangeChange('colorRampMax', e.target.value)}
                    />
                  </Form.Group>
                </Col>
              </Row>
            )}
          </Col>
        </Row>
      </Form>
    </div>
  );
};

export default GriddedControls;
