/**
 * ConfigurationsSummaryTab
 *
 * Layout:  map (top ~1/3) | scrollable table of configurations_summary rows (bottom ~2/3)
 *
 * Behaviour
 * ---------
 * - Loads configurations_summary on mount and populates the table.
 * - Clicking a table row fetches the corresponding location geometries from
 *   configurations_by_location and shows them as points on the map.
 * - The selected row is highlighted in the table.
 */
import { useEffect, useState, useCallback } from 'react';
import { Spinner, Alert } from 'react-bootstrap';
import SimpleMapPanel from './SimpleMapPanel';
import { apiService } from '../../../services/api';
import { useSortableTable } from '../../../hooks/useSortableTable.jsx';

// ── Helpers ────────────────────────────────────────────────────────────────
const fmt = (val) => {
  if (val == null) return '—';
  return String(val).replace('T', ' ').replace(/\.\d+Z?$/, '');
};

// Returns a raw sortable value for a column key
const sortValue = (row, key) => {
  if (key === 'n_locations') return row.n_locations ?? 0;
  return String(row[key] ?? '').toLowerCase();
};

// ── Component ──────────────────────────────────────────────────────────────
const COLUMNS = [
  { key: 'configuration_name', label: 'Configuration' },
  { key: 'variable_name',      label: 'Variable' },
  { key: 'n_locations',        label: '# Locations' },
  { key: 'unit_name',          label: 'Unit' },
  { key: 'timeseries_type',    label: 'Type' },
  { key: 'min_value_time',     label: 'Value Time Min' },
  { key: 'max_value_time',     label: 'Value Time Max' },
  { key: 'min_reference_time', label: 'Reference Time Min' },
  { key: 'max_reference_time', label: 'Reference Time Max' },
  { key: 'description',        label: 'Description' },
];

// Popup HTML for locations belonging to selected config
const makePopupHTML = (props) => `
  <div style="padding:6px 10px;font-size:0.83rem;line-height:1.4;">
    <div style="font-weight:600;margin-bottom:2px;">${props.name || props.primary_location_id || ''}</div>
    <div><strong>ID:</strong> ${props.primary_location_id || '—'}</div>
  </div>
`;

const ConfigurationsSummaryTab = ({ isActive = true }) => {
  const [rows, setRows]                 = useState([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);
  const [selectedRow, setSelectedRow]   = useState(null);
  const [mapLocations, setMapLocations] = useState(null);
  const [mapLoading, setMapLoading]     = useState(false);

  const { sortedRows, handleSort, SortIcon } = useSortableTable(rows, 'configuration_name', sortValue);

  // Load summary table on mount
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    apiService.getConfigurationsTable()
      .then((data) => {
        if (cancelled) return;
        const items = Array.isArray(data)
          ? data
          : Array.isArray(data.items) ? data.items : (data.features || []).map((f) => f.properties ?? f);
        setRows(items);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, []);

  // Fetch locations for the clicked row
  const handleRowClick = useCallback((row) => {
    const key = `${row.configuration_name}||${row.variable_name}`;
    if (selectedRow === key) {
      // Deselect
      setSelectedRow(null);
      setMapLocations(null);
      return;
    }
    setSelectedRow(key);
    setMapLoading(true);

    apiService.getConfigurationsByLocationGeojson({ configuration_name: row.configuration_name })
      .then((geojson) => {
        setMapLocations(geojson);
      })
      .catch((err) => {
        console.error('ConfigurationsSummaryTab: Failed to load locations:', err);
        setMapLocations(null);
      })
      .finally(() => setMapLoading(false));
  }, [selectedRow]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Map — top 1/3 */}
      <div style={{ flex: '1 1 0', minHeight: 0, position: 'relative' }}>
        <SimpleMapPanel
          locations={mapLocations}
          getPopupHTML={makePopupHTML}
          isActive={isActive}
        />
        {mapLoading && (
          <div
            className="position-absolute top-50 start-50 translate-middle text-center"
            style={{ zIndex: 10 }}
          >
            <div className="spinner-border spinner-border-sm text-primary" role="status" />
            <div className="small text-muted mt-1">Loading locations…</div>
          </div>
        )}
        {!selectedRow && !mapLoading && (
          <div
            className="position-absolute top-50 start-50 translate-middle text-center text-muted"
            style={{ zIndex: 5, pointerEvents: 'none', background: 'rgba(255,255,255,0.7)', borderRadius: 6, padding: '6px 12px' }}
          >
            <small>Click a configuration row below to view its locations</small>
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={{ flex: '0 0 1px', background: '#dee2e6' }} />

      {/* Table — bottom 2/3 */}
      <div style={{ flex: '1 1 0', minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {loading && (
          <div className="d-flex align-items-center justify-content-center h-100">
            <Spinner animation="border" variant="primary" role="status">
              <span className="visually-hidden">Loading configurations…</span>
            </Spinner>
          </div>
        )}

        {error && (
          <Alert variant="danger" className="m-2">
            <i className="bi bi-exclamation-triangle-fill me-2" />
            {error}
          </Alert>
        )}

        {!loading && !error && rows.length === 0 && (
          <div className="d-flex align-items-center justify-content-center h-100 text-muted">
            <span>No configurations available.</span>
          </div>
        )}

        {!loading && !error && rows.length > 0 && (
          <div style={{ overflowY: 'auto', flex: 1 }}>
            <table className="table table-sm table-bordered table-hover mb-0" style={{ fontSize: '0.82rem' }}>
              <thead className="table-light sticky-top">
                <tr>
                  {COLUMNS.map((c) => {
                    return (
                      <th
                        key={c.key}
                        onClick={() => handleSort(c.key)}
                        style={{ whiteSpace: 'nowrap', verticalAlign: 'middle', cursor: 'pointer', userSelect: 'none' }}
                        title={`Sort by ${c.label}`}
                      >
                        {c.label}<SortIcon colKey={c.key} />
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, i) => {
                  const key = `${row.configuration_name}||${row.variable_name}`;
                  const isSelected = selectedRow === key;
                  return (
                    <tr
                      key={i}
                      onClick={() => handleRowClick(row)}
                      style={{ cursor: 'pointer', background: isSelected ? '#cfe2ff' : undefined }}
                      className={isSelected ? 'table-primary' : ''}
                    >
                      {COLUMNS.map((c) => {
                        let val;
                        if (['min_value_time', 'max_value_time', 'min_reference_time', 'max_reference_time'].includes(c.key)) {
                          val = fmt(row[c.key]);
                        } else {
                          val = row[c.key] ?? '—';
                        }
                        return (
                          <td key={c.key} style={{ verticalAlign: 'middle', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={String(val)}>
                            {c.key === 'configuration_name' && isSelected
                              ? <strong>{val}</strong>
                              : String(val)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ConfigurationsSummaryTab;
