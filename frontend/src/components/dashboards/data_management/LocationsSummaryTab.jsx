/**
 * LocationsSummaryTab
 *
 * Layout:  map (top ~1/3) | scrollable table (bottom ~2/3)
 *
 * Behaviour
 * ---------
 * - Loads tabular rows from locations_with_attributes on mount.
 * - Clicking a table row plots that single location as a point on the map.
 * - Table rows show: location id, name, and various location attributes.
 */
import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
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
  const value = row[key];

  if (value == null) return '';
  if (typeof value === 'number') return value;

  const stringValue = String(value).trim();
  if (stringValue === '') return '';

  const numericValue = Number(stringValue);
  if (!Number.isNaN(numericValue)) return numericValue;

  return stringValue.toLowerCase();
};

// Default columns always shown
const DEFAULT_COLUMNS = [
  { key: 'location_id',        label: 'Location ID' },
  { key: 'name',               label: 'Name' },
  { key: 'state_name',         label: 'State' },
  { key: 'drainage_area_km2',  label: 'Drainage Area (km²)' },
  { key: 'slope_mean_percent', label: 'Mean Slope (%)' },
  { key: 'rfc',                label: 'RFC' },
];

// Default attribute names fetched from location_attributes on initial load
const DEFAULT_ATTRIBUTE_NAMES = ['state_name', 'drainage_area_km2', 'slope_mean_percent', 'rfc'];

// Pivot EAV rows [{location_id, attribute_name, value}] into a map keyed by location_id
const pivotAttributes = (items) => {
  const map = {};
  (items || []).forEach((item) => {
    if (!map[item.location_id]) map[item.location_id] = {};
    map[item.location_id][item.attribute_name] = item.value;
  });
  return map;
};

// Popup content for map hover
const makePopupHTML = (props) => {
  return `
    <div style="padding:6px 10px;font-size:0.83rem;line-height:1.5;max-height:260px;overflow-y:auto;">
      <div style="font-weight:600;margin-bottom:2px;">${props.name || '—'}</div>
      <div><strong>ID:</strong> ${props.location_id || '—'}</div>
      ${props.state_name ? `<div><strong>State:</strong> ${props.state_name}</div>` : ''}
      ${props.rfc ? `<div><strong>RFC:</strong> ${props.rfc}</div>` : ''}
    </div>
  `;
};

// ── Component ──────────────────────────────────────────────────────────────
const LocationsSummaryTab = ({ isActive = true }) => {
  const [geojson, setGeojson]           = useState(null);
  const [basinGeojson, setBasinGeojson] = useState(null);
  const [basinChecked, setBasinChecked] = useState(false);
  const [noGeometry, setNoGeometry]     = useState(false);
  const [rows, setRows]                 = useState([]);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState(null);
  const [selectedId, setSelectedId]     = useState(null);

  // Side panel state for configurations
  const [sidePanelOpen, setSidePanelOpen] = useState(false);
  const [sidePanelLocationId, setSidePanelLocationId] = useState(null);
  const [sidePanelConfigs, setSidePanelConfigs] = useState([]);
  const [sidePanelLoading, setSidePanelLoading] = useState(false);
  const [sidePanelError, setSidePanelError] = useState(null);

  // Column picker state
  const [activeColumns, setActiveColumns]   = useState(DEFAULT_COLUMNS);
  const [availableAttributes, setAvailableAttributes] = useState([]);
  const [pickerOpen, setPickerOpen]         = useState(false);
  const [checkedKeys, setCheckedKeys]       = useState(new Set());
  const pickerRef                           = useRef(null);

  // Load available attribute names from the attributes table on mount
  useEffect(() => {
    apiService.getAttributes()
      .then((data) => {
        const defaultKeys = new Set(DEFAULT_COLUMNS.map((c) => c.key));
        const attrs = (data?.items || [])
          .filter((item) => !defaultKeys.has(item.name))
          .map((item) => ({ key: item.name, label: item.description || item.name }))
          .sort((a, b) => a.label.localeCompare(b.label));
        setAvailableAttributes(attrs);
      })
      .catch(() => { /* non-fatal: picker will be empty */ });
  }, []);

  // Close picker when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target)) setPickerOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const toggleCheck = (key) => setCheckedKeys((prev) => {
    const next = new Set(prev);
    next.has(key) ? next.delete(key) : next.add(key);
    return next;
  });

  const handleAddToTable = () => {
    if (checkedKeys.size === 0) return;
    const toAdd = availableAttributes.filter(
      (c) => checkedKeys.has(c.key) && !activeColumns.find((a) => a.key === c.key)
    );
    if (toAdd.length === 0) { setPickerOpen(false); return; }
    const newColumns = [...activeColumns, ...toAdd];
    setActiveColumns(newColumns);
    setCheckedKeys(new Set());
    setPickerOpen(false);
    // Re-fetch with updated set of attribute names
    const extraAttributeNames = newColumns
      .filter((c) => !DEFAULT_COLUMNS.find((d) => d.key === c.key))
      .map((c) => c.key);
    fetchRows(extraAttributeNames);
  };

  const handleRemoveColumn = (key) => {
    setActiveColumns((prev) => prev.filter((c) => c.key !== key));
  };

  // Already-added optional keys (to show as added in the picker)
  const addedOptionalKeys = new Set(activeColumns.map((c) => c.key));

  const { sortedRows, handleSort, SortIcon } = useSortableTable(rows, 'location_id', sortValue);

  const [filterColumn, setFilterColumn] = useState('');
  const [filterText, setFilterText] = useState('');

  const filteredRows = useMemo(() => {
    if (!filterText.trim()) return sortedRows;
    const q = filterText.trim().toLowerCase();
    if (filterColumn) {
      return sortedRows.filter((row) => String(row[filterColumn] ?? '').toLowerCase().includes(q));
    }
    return sortedRows.filter((row) =>
      activeColumns.some((col) => String(row[col.key] ?? '').toLowerCase().includes(q))
    );
  }, [sortedRows, filterText, filterColumn, activeColumns]);

  const hasActiveFilter = !!filterText;

  // Load tabular rows by fetching locations (id + name) and location_attributes
  // for the given attribute names, then pivoting and joining in the frontend.
  const fetchRows = useCallback((extraAttributeNames = []) => {
    const attributeNames = [...DEFAULT_ATTRIBUTE_NAMES, ...extraAttributeNames];
    setLoading(true);
    setError(null);
    Promise.all([
      apiService.getLocationIdNames('usgs', 5000),
      apiService.getLocationAttributesByNames(attributeNames),
    ])
      .then(([locationsData, attrsData]) => {
        const locItems = locationsData?.items || [];
        const attrItems = attrsData?.items || [];
        const attrMap = pivotAttributes(attrItems);
        const joined = locItems.map((loc) => ({
          location_id: loc.id,
          name: loc.name,
          ...(attrMap[loc.id] || {}),
        }));
        setRows(joined);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  // On row click: fetch geometry from the locations table and full row data from
  // configurations_by_location in parallel, then merge for the map popup.
  const handleRowClick = useCallback((row) => {
    if (selectedId === row.location_id) {
      setSelectedId(null);
      setGeojson(null);
      setBasinGeojson(null);
      setBasinChecked(false);
      setNoGeometry(false);
      return;
    }
    setSelectedId(row.location_id);
    setBasinChecked(false);
    setNoGeometry(false);
    const basinId = row.location_id.replace(/^usgs-/, 'usgsbasin-');
    Promise.all([
      apiService.getLocationById(row.location_id),
      apiService.getLocationById(basinId).catch(() => null),
    ])
      .then(([locationData, basinData]) => {
        const feature = locationData?.features?.[0];
        if (!feature) {
          setNoGeometry(true);
          setBasinChecked(true);
          return;
        }
        const merged = {
          type: 'FeatureCollection',
          features: [{
            ...feature,
            properties: {
              ...feature.properties,
              location_id: row.location_id,
              name: row.name,
            },
          }],
        };
        setGeojson(merged);
        const hasBasin = !!(basinData?.features?.length);
        setBasinGeojson(hasBasin ? basinData : null);
        setBasinChecked(true);
      })
      .catch(() => { setBasinChecked(true); });
  }, [selectedId]);

  // Handle click on map point — fetch configurations for that location
  const handleMapPointClick = useCallback((properties) => {
    const locId = properties.location_id;
    console.log('[DEBUG] Map point clicked with location_id:', locId, 'full properties:', properties);
    setSidePanelLocationId(locId);
    setSidePanelOpen(true);
    setSidePanelLoading(true);
    setSidePanelError(null);
    apiService.getConfigurationsByLocationId(locId)
      .then((data) => {
        console.log('[DEBUG] Configurations received:', data);
        const items = Array.isArray(data)
          ? data
          : Array.isArray(data.items) ? data.items : [];
        setSidePanelConfigs(items);
      })
      .catch((err) => {
        console.error('[ERROR] Failed to load configurations:', err);
        setSidePanelError(err.message);
      })
      .finally(() => setSidePanelLoading(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Map + Side Panel — top 1/3 */}
      <div style={{ flex: '1 1 0', minHeight: 0, display: 'flex', position: 'relative' }}>
        {/* Map */}
        <div style={{ flex: sidePanelOpen ? '1 1 0' : '1 1 100%', minWidth: 0, minHeight: 0, position: 'relative' }}>
          <SimpleMapPanel
            locations={geojson}
            basinLocations={basinGeojson}
            getPopupHTML={makePopupHTML}
            onPointClick={handleMapPointClick}
            isActive={isActive}
          />
          {!selectedId && (
            <div
              className="position-absolute top-50 start-50 translate-middle text-center text-muted"
              style={{ zIndex: 5, pointerEvents: 'none', background: 'rgba(255,255,255,0.7)', borderRadius: 6, padding: '6px 12px' }}
            >
              <small>Click a location row below to view it on the map</small>
            </div>
          )}
          {selectedId && noGeometry && (
            <div
              className="position-absolute top-50 start-50 translate-middle text-center text-muted"
              style={{ zIndex: 5, pointerEvents: 'none', background: 'rgba(255,255,255,0.82)', borderRadius: 6, padding: '6px 12px' }}
            >
              <small><i className="bi bi-exclamation-circle me-1" />No geometry found for this location</small>
            </div>
          )}
        </div>

        {/* Side panel for configurations */}
        {sidePanelOpen && (
          <div style={{ flex: '0 0 50%', minHeight: 0, borderLeft: '1px solid #dee2e6', display: 'flex', flexDirection: 'column', background: '#fff' }}>
            {/* Header */}
            <div style={{ flex: '0 0 auto', padding: '8px 12px', borderBottom: '1px solid #dee2e6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong style={{ fontSize: '0.9rem' }}>Configurations</strong>
              <button
                type="button"
                className="btn-close"
                style={{ padding: 0 }}
                onClick={() => setSidePanelOpen(false)}
                aria-label="Close"
              />
            </div>

            {/* Content */}
            {sidePanelLoading && (
              <div className="d-flex align-items-center justify-content-center h-100">
                <Spinner animation="border" variant="primary" role="status" style={{ width: '1.5rem', height: '1.5rem' }}>
                  <span className="visually-hidden">Loading…</span>
                </Spinner>
              </div>
            )}

            {sidePanelError && (
              <Alert variant="danger" className="m-2 mb-0" style={{ flex: '0 0 auto', fontSize: '0.8rem' }}>
                <i className="bi bi-exclamation-triangle-fill me-2" />
                {sidePanelError}
              </Alert>
            )}

            {!sidePanelLoading && !sidePanelError && sidePanelConfigs.length === 0 && (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <small>No configurations found</small>
              </div>
            )}

            {!sidePanelLoading && !sidePanelError && sidePanelConfigs.length > 0 && (
              <div style={{ flex: '1 1 0', minHeight: 0, overflowY: 'auto' }}>
                <table className="table table-sm table-bordered mb-0" style={{ fontSize: '0.75rem' }}>
                  <thead className="table-light sticky-top">
                    <tr>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Configuration</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Variable</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Unit</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Ref Min</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Ref Max</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Val Min</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}>Val Max</th>
                      <th style={{ whiteSpace: 'nowrap', verticalAlign: 'middle' }}># Members</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sidePanelConfigs.map((config, i) => (
                      <tr key={i}>
                        <td title={config.configuration_name}>{config.configuration_name}</td>
                        <td title={config.variable_name}>{config.variable_name}</td>
                        <td title={config.unit_name}>{config.unit_name}</td>
                        <td>{fmt(config.min_reference_time)}</td>
                        <td>{fmt(config.max_reference_time)}</td>
                        <td>{fmt(config.min_value_time)}</td>
                        <td>{fmt(config.max_value_time)}</td>
                        <td>{config.num_members ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Divider */}
      <div style={{ flex: '0 0 1px', background: '#dee2e6' }} />

      {/* Table toolbar + Table */}
      <div style={{ flex: '1 1 0', minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

        {/* Column picker toolbar */}
        <div ref={pickerRef} style={{ flex: '0 0 auto', padding: '4px 8px', borderBottom: '1px solid #dee2e6', position: 'relative', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            className="btn btn-sm btn-outline-secondary"
            style={{ fontSize: '0.8rem' }}
            onClick={() => setPickerOpen((o) => !o)}
          >
            <i className="bi bi-columns-gap me-1" />
            Add columns {pickerOpen ? '▲' : '▼'}
          </button>
          {/* Pills for added optional columns */}
          {activeColumns.filter((c) => !DEFAULT_COLUMNS.find((d) => d.key === c.key)).map((c) => (
            <span key={c.key} className="badge bg-primary d-flex align-items-center" style={{ fontSize: '0.75rem', gap: 4 }}>
              {c.label}
              <button
                type="button"
                className="btn-close btn-close-white"
                style={{ fontSize: '0.6rem' }}
                onClick={() => handleRemoveColumn(c.key)}
                aria-label={`Remove ${c.label}`}
              />
            </span>
          ))}

          {/* Dropdown panel */}
          {pickerOpen && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                zIndex: 1050,
                background: '#fff',
                border: '1px solid #dee2e6',
                borderRadius: 6,
                boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
                width: 340,
                maxHeight: 360,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div style={{ padding: '6px 10px', borderBottom: '1px solid #dee2e6', fontWeight: 600, fontSize: '0.82rem' }}>
                Select columns to add
              </div>
              <div style={{ overflowY: 'auto', flex: 1, padding: '4px 0' }}>
                {availableAttributes.map((c) => {
                  const alreadyAdded = addedOptionalKeys.has(c.key);
                  return (
                    <label
                      key={c.key}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '3px 12px',
                        fontSize: '0.82rem',
                        cursor: alreadyAdded ? 'default' : 'pointer',
                        color: alreadyAdded ? '#aaa' : 'inherit',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={alreadyAdded || checkedKeys.has(c.key)}
                        disabled={alreadyAdded}
                        onChange={() => toggleCheck(c.key)}
                      />
                      {c.label}
                      {alreadyAdded && <span style={{ fontSize: '0.72rem', color: '#aaa' }}>(added)</span>}
                    </label>
                  );
                })}
              </div>
              <div style={{ padding: '6px 10px', borderTop: '1px solid #dee2e6', display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
                <button className="btn btn-sm btn-outline-secondary" onClick={() => { setCheckedKeys(new Set()); setPickerOpen(false); }}>Cancel</button>
                <button className="btn btn-sm btn-primary" onClick={handleAddToTable} disabled={checkedKeys.size === 0}>Add to table</button>
              </div>
            </div>
          )}
        </div>
        {/* Filter bar */}
        <div style={{ flex: '0 0 auto', padding: '4px 8px', borderBottom: '1px solid #dee2e6', display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#495057' }}>Filter:</span>
          <select
            className="form-select form-select-sm"
            value={filterColumn}
            onChange={(e) => { setFilterColumn(e.target.value); setFilterText(''); }}
            style={{ width: 160 }}
          >
            <option value="">— All columns —</option>
            {activeColumns.map((col) => (
              <option key={col.key} value={col.key}>{col.label}</option>
            ))}
          </select>
          <input
            type="text"
            className="form-control form-control-sm"
            placeholder={
              filterColumn
                ? `Filter by ${activeColumns.find((c) => c.key === filterColumn)?.label ?? filterColumn}…`
                : 'Search all columns…'
            }
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            style={{ width: 220 }}
          />
          {hasActiveFilter && (
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={() => { setFilterText(''); setFilterColumn(''); }}
              style={{ fontSize: '0.8rem' }}
            >
              Clear
            </button>
          )}
          {rows.length > 0 && (
            <span className="text-muted ms-auto" style={{ fontSize: '0.78rem' }}>
              {filteredRows.length} / {rows.length} rows
            </span>
          )}
        </div>

        {loading && (
          <div className="d-flex align-items-center justify-content-center h-100">
            <Spinner animation="border" variant="primary" role="status">
              <span className="visually-hidden">Loading locations…</span>
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
            <span>No locations available.</span>
          </div>
        )}

        {!loading && !error && rows.length > 0 && (
          <div style={{ overflowX: 'auto', overflowY: 'auto', flex: 1 }}>
            <table className="table table-sm table-bordered table-hover mb-0" style={{ fontSize: '0.82rem' }}>
              <thead className="table-light sticky-top">
                <tr>
                  {activeColumns.map((c) => (
                    <th
                      key={c.key}
                      onClick={() => handleSort(c.key)}
                      style={{ whiteSpace: 'nowrap', verticalAlign: 'middle', cursor: 'pointer', userSelect: 'none' }}
                      title={`Sort by ${c.label}`}
                    >
                      {c.label}<SortIcon colKey={c.key} />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredRows.map((row, i) => (
                  <tr
                    key={i}
                    onClick={() => handleRowClick(row)}
                    style={{ cursor: 'pointer' }}
                    className={selectedId === row.location_id ? 'table-primary' : ''}
                  >
                    {activeColumns.map((c) => {
                      let val;
                      if (c.key === 'min_reference_time' || c.key === 'max_reference_time') {
                        val = fmt(row[c.key]);
                      } else {
                        val = row[c.key] ?? '—';
                      }
                      return (
                        <td
                          key={c.key}
                          style={{
                            verticalAlign: 'middle',
                            maxWidth: 280,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                          title={String(val)}
                        >
                          {String(val)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default LocationsSummaryTab;
