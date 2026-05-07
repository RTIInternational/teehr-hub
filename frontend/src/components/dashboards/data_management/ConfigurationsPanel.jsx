import { useState } from 'react';
import { Spinner, Alert, Form, Table } from 'react-bootstrap';

const formatDatetime = (val) => {
  if (!val) return '—';
  return String(val).replace('T', ' ').replace(/\.\d+Z?$/, '');
};

const FIELD_LABELS = [
  { key: 'configuration_name', label: 'Configuration' },
  { key: 'variable_name', label: 'Variable' },
  { key: 'unit_name', label: 'Unit' },
  { key: 'timeseries_type', label: 'Type' },
  { key: 'location_id_prefix', label: 'Location Prefix' },
  { key: 'n_locations', label: '# Locations' },
  { key: 'min_reference_time', label: 'Min Reference Time' },
  { key: 'max_reference_time', label: 'Max Reference Time' },
  { key: 'min_value_time', label: 'Min Value Time' },
  { key: 'max_value_time', label: 'Max Value Time' },
  { key: 'description', label: 'Description' },
  { key: 'created_at', label: 'Created At' },
  { key: 'updated_at', label: 'Updated At' },
];

const DATETIME_KEYS = new Set([
  'min_reference_time', 'max_reference_time',
  'min_value_time', 'max_value_time',
  'created_at', 'updated_at',
]);

const ConfigurationsPanel = ({ configurations = [], loading = false, error = null }) => {
  const [selected, setSelected] = useState('');

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

  const cfg = configurations.find((c) => c.configuration_name === selected) ?? null;

  return (
    <div className="d-flex flex-column h-100" style={{ overflow: 'hidden' }}>
      <div className="px-3 pt-3 pb-2 border-bottom">
        <h6 className="mb-2 fw-semibold">Configurations</h6>
        <Form.Select
          size="sm"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          aria-label="Select configuration"
        >
          <option value="">— Select a configuration —</option>
          {configurations.map((c) => (
            <option key={c.configuration_name} value={c.configuration_name}>
              {c.configuration_name}
            </option>
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
                    {key === 'configuration_name'
                      ? <code>{cfg[key] ?? '—'}</code>
                      : DATETIME_KEYS.has(key)
                        ? formatDatetime(cfg[key])
                        : cfg[key] ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <div className="d-flex align-items-center justify-content-center h-100 text-muted">
            <span>Select a configuration to view details.</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConfigurationsPanel;
