import { useState } from 'react';
import { Spinner, Alert, Form, Table } from 'react-bootstrap';

const formatDatetime = (val) => {
  if (!val) return '—';
  return String(val).replace('T', ' ').replace(/\.\d+Z?$/, '');
};

const FIELD_LABELS = [
  { key: 'description', label: 'Description' },
  { key: 'timeseries_type', label: 'Type' },
  { key: 'location_id_prefix', label: 'Location Prefix' },
  { key: 'n_locations', label: '# Locations' },
  { key: 'reference_time_range', label: 'Reference Time' },
  { key: 'value_time_range', label: 'Value Time' },
  { key: 'created_at', label: 'Created At' },
  { key: 'updated_at', label: 'Updated At' },
];

const DATETIME_KEYS = new Set(['created_at', 'updated_at']);

const formatRange = (min, max) => {
  const a = formatDatetime(min);
  const b = formatDatetime(max);
  if (!min && !max) return '—';
  if (!min) return `— to ${b}`;
  if (!max) return `${a} to —`;
  return `${a} – ${b}`;
};

const ConfigurationsPanel = ({ configurations = [], loading = false, error = null, onSelect = null, onGenerate = null, canGenerate = false }) => {
  const [selectedConfig, setSelectedConfig] = useState('');
  const [selectedVariable, setSelectedVariable] = useState('');
  const [selectedUnit, setSelectedUnit] = useState('');

  if (loading) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100">
        <Spinner animation="border" variant="primary" role="status">
          <span className="visually-hidden">Loading configurations...</span>
        </Spinner>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="danger" className="m-2">
        <i className="bi bi-exclamation-triangle-fill me-2"></i>
        {error}
      </Alert>
    );
  }

  if (configurations.length === 0) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted">
        <span>No configurations available.</span>
      </div>
    );
  }

  // Unique configuration names
  const configNames = [...new Set(configurations.map((c) => c.configuration_name))].sort();

  // Variable names for the selected configuration
  const variableNames = selectedConfig
    ? [...new Set(
        configurations
          .filter((c) => c.configuration_name === selectedConfig)
          .map((c) => c.variable_name)
      )].sort()
    : [];

  // Unit names for the selected configuration + variable
  const unitNames = selectedConfig && selectedVariable
    ? [...new Set(
        configurations
          .filter((c) => c.configuration_name === selectedConfig && c.variable_name === selectedVariable)
          .map((c) => c.unit_name)
      )].sort()
    : [];

  // The matching row for the detail table
  const cfg = selectedConfig && selectedVariable && selectedUnit
    ? (configurations.find(
        (c) =>
          c.configuration_name === selectedConfig &&
          c.variable_name === selectedVariable &&
          c.unit_name === selectedUnit
      ) ?? null)
    : null;

  const handleConfigChange = (value) => {
    setSelectedConfig(value);
    setSelectedVariable('');
    setSelectedUnit('');
    if (onSelect) onSelect(null);
  };

  const handleVariableChange = (value) => {
    setSelectedVariable(value);
    setSelectedUnit('');
    if (onSelect) onSelect(null);
  };

  const handleUnitChange = (value) => {
    setSelectedUnit(value);
    if (onSelect) {
      const match = configurations.find(
        (c) =>
          c.configuration_name === selectedConfig &&
          c.variable_name === selectedVariable &&
          c.unit_name === value
      ) ?? null;
      onSelect(match);
    }
  };

  return (
    <div className="d-flex flex-column h-100" style={{ overflow: 'hidden' }}>
      <div className="px-3 pt-3 pb-2 border-bottom">
        <h6 className="mb-2 fw-semibold">Configurations</h6>
        <Form.Select
          size="sm"
          value={selectedConfig}
          onChange={(e) => handleConfigChange(e.target.value)}
          aria-label="Select configuration"
          className="mb-2"
        >
          <option value="">— Select a configuration —</option>
          {configNames.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>
        <Form.Select
          size="sm"
          value={selectedVariable}
          onChange={(e) => handleVariableChange(e.target.value)}
          aria-label="Select variable"
          disabled={!selectedConfig}
          className="mb-2"
        >
          <option value="">— Select a variable —</option>
          {variableNames.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>
        <Form.Select
          size="sm"
          value={selectedUnit}
          onChange={(e) => handleUnitChange(e.target.value)}
          aria-label="Select unit"
          disabled={!selectedVariable}
        >
          <option value="">— Select a unit —</option>
          {unitNames.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </Form.Select>
      </div>
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {cfg ? (
          <Table bordered size="sm" className="mb-0">
            <tbody>
              {FIELD_LABELS.map(({ key, label }) => (
                <tr key={key}>
                  <th className="table-light" style={{ whiteSpace: 'nowrap', width: '40%' }}>{label}</th>
                  <td>
                    {key === 'reference_time_range'
                      ? formatRange(cfg.min_reference_time, cfg.max_reference_time)
                      : key === 'value_time_range'
                        ? formatRange(cfg.min_value_time, cfg.max_value_time)
                        : DATETIME_KEYS.has(key)
                          ? formatDatetime(cfg[key])
                          : cfg[key] ?? '—'}
                  </td>
                </tr>
              ))}
              {cfg.n_members != null && (
                <tr>
                  <th className="table-light" style={{ whiteSpace: 'nowrap', width: '40%' }}># Members</th>
                  <td>{cfg.n_members}</td>
                </tr>
              )}
              {Array.isArray(cfg.members) && cfg.members.length > 0 && (
                <tr>
                  <th className="table-light" style={{ whiteSpace: 'nowrap', verticalAlign: 'top' }}>Members</th>
                  <td style={{ fontSize: '0.8rem' }}>
                    {cfg.members.map((m) => (
                      <span key={m} className="badge bg-secondary me-1 mb-1" style={{ fontWeight: 'normal' }}>{m}</span>
                    ))}
                  </td>
                </tr>
              )}
            </tbody>
          </Table>
        ) : (
          <div className="d-flex align-items-center justify-content-center h-100 text-muted">
            <span>Select a configuration, variable, and unit to view details.</span>
          </div>
        )}
      </div>
      <div style={{ padding: '8px 12px', borderTop: '1px solid #e0e0e0', flexShrink: 0 }}>
        <button
          className="btn btn-primary btn-sm w-100"
          style={{ height: '28px', fontSize: '0.75rem', padding: '0 12px' }}
          disabled={!canGenerate}
          onClick={onGenerate}
        >
          Generate Completeness Heatmap
        </button>
      </div>
    </div>
  );
};

export default ConfigurationsPanel;
