/**
 * LocationsSummaryTab
 *
 * Layout:  map (top ~1/3) | scrollable table (bottom ~2/3)
 *
 * Behaviour
 * ---------
 * - Loads tabular rows from configurations_by_location on mount.
 * - Clicking a table row plots that single location as a point on the map.
 * - Table rows show: location id, name, configuration names, variable names,
 *   unit names, and value time range.
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
  if (key === 'min_value_time' || key === 'max_value_time') return row[key] ?? '';
  return String(row[key] ?? '').toLowerCase();
};

// Parse a field that MapLibre may have serialized to a JSON string
const parseArrayProp = (val) => {
  if (Array.isArray(val)) return val;
  if (typeof val === 'string') {
    try { const p = JSON.parse(val); return Array.isArray(p) ? p : [val]; } catch { return [val]; }
  }
  return val ? [String(val)] : [];
};

// Default columns always shown
const DEFAULT_COLUMNS = [
  { key: 'primary_location_id', label: 'Location ID' },
  { key: 'name',                label: 'Name' },
  { key: 'state',               label: 'State' },
  { key: 'drainage_area_km2',   label: 'Drainage Area (km²)' },
  { key: 'slope_mean_percent',  label: 'Mean Slope (%)' },
  { key: 'min_value_time',      label: 'Value Time Min' },
  { key: 'max_value_time',      label: 'Value Time Max' },
];

// All optional columns the user can add
const OPTIONAL_COLUMNS = [
  { key: 'min_reference_time',    label: 'Reference Time Min' },
  { key: 'max_reference_time',    label: 'Reference Time Max' },
  { key: 'num_timeseries',        label: '# Timeseries' },
  { key: 'is_active',             label: 'Active' },
  { key: 'has_inst_discharge',    label: 'Inst Discharge' },
  { key: 'has_inst_stage',        label: 'Inst Stage' },
  { key: 'has_mean_daily_discharge', label: 'Mean Daily Discharge' },
  { key: 'has_max_daily_discharge',  label: 'Max Daily Discharge' },
  { key: 'has_mean_daily_stage',  label: 'Mean Daily Stage' },
  { key: 'has_max_daily_stage',   label: 'Max Daily Stage' },
  { key: 'site_type_code',        label: 'Site Type' },
  { key: 'state_name',            label: 'State Name' },
  { key: 'county',                label: 'County' },
  { key: 'county_name',           label: 'County Name' },
  { key: 'nws_region',            label: 'NWS Region' },
  { key: 'wfo',                   label: 'WFO' },
  { key: 'rfc',                   label: 'RFC' },
  { key: 'rfc_action_flow_cms',   label: 'RFC Action Flow (cms)' },
  { key: 'rfc_minor_flow_cms',    label: 'RFC Minor Flow (cms)' },
  { key: 'rfc_moderate_flow_cms', label: 'RFC Moderate Flow (cms)' },
  { key: 'rfc_major_flow_cms',    label: 'RFC Major Flow (cms)' },
  { key: 'nwm30_calb',            label: 'NWM30 Calibrated' },
  { key: 'disturbance_index',     label: 'Disturbance Index' },
  { key: 'gagesII_class',         label: 'Gages II Class' },
  { key: 'huc2',                  label: 'HUC2' },
  { key: 'huc4',                  label: 'HUC4' },
  { key: 'huc6',                  label: 'HUC6' },
  { key: 'huc8',                  label: 'HUC8' },
  { key: 'huc10',                 label: 'HUC10' },
  { key: 'huc12',                 label: 'HUC12' },
  { key: 'drainage_area',         label: 'Drainage Area (native)' },
  { key: 'elev_mean_m',           label: 'Mean Elevation (m)' },
  { key: 'relief_ratio',          label: 'Relief Ratio' },
  { key: 'stream_order',          label: 'Stream Order' },
  { key: 'sinuousity',            label: 'Sinuosity' },
  { key: 'topo_wetness_index',    label: 'Topo Wetness Index' },
  { key: 'runoff_ratio',          label: 'Runoff Ratio' },
  { key: 'runoff_mean_mm',        label: 'Mean Runoff (mm)' },
  { key: 'bfi_mean',              label: 'BFI Mean' },
  { key: 'horton_percent',        label: 'Horton (%)' },
  { key: 'pcpn_mean_mm',          label: 'Mean Precip (mm)' },
  { key: 'pcpn_percent_snow',     label: 'Precip Snow (%)' },
  { key: 'temp_mean_c',           label: 'Mean Temp (°C)' },
  { key: 'q10_cms',               label: 'Q10 (cms)' },
  { key: 'q50_cms',               label: 'Q50 (cms)' },
  { key: 'q90_cms',               label: 'Q90 (cms)' },
  { key: 'max_record',            label: 'Max Record' },
  { key: 'first_year',            label: 'First Year' },
  { key: 'last_year',             label: 'Last Year' },
  { key: 'season_index',          label: 'Season Index' },
  { key: 'percent_imperv',        label: 'Imperv (%)' },
  { key: 'percent_irrig',         label: 'Irrigated (%)' },
  { key: 'percent_developed',     label: 'Developed (%)' },
  { key: 'percent_canals',        label: 'Canals (%)' },
  { key: 'ndams',                 label: 'Dams' },
  { key: 'ndams_major',           label: 'Major Dams' },
  { key: 'ndams_major_100km2',    label: 'Major Dams/100km²' },
  { key: 'ndams_100km2',          label: 'Dams/100km²' },
  { key: 'dam_dist_nearest_km',   label: 'Nearest Dam (km)' },
  { key: 'storage_max_Mlkm2',     label: 'Max Storage (Ml/km²)' },
  { key: 'storage_normal_Mlkm2',  label: 'Normal Storage (Ml/km²)' },
  { key: 'withdrawals_Mlkm2',     label: 'Withdrawals (Ml/km²)' },
  { key: 'aggecoregion',          label: 'Agg Ecoregion' },
  { key: 'ecoregion_L2',          label: 'Ecoregion L2' },
  { key: 'epa_ecoregion_l1',      label: 'EPA Ecoregion L1' },
  { key: 'epa_ecoregion_l2',      label: 'EPA Ecoregion L2' },
  { key: 'iana_timezone',         label: 'IANA Timezone' },
  { key: 'timezone',              label: 'Timezone' },
];

// Popup content for map hover
const makePopupHTML = (props) => {
  const cfgNames = [...parseArrayProp(props.configuration_names)].sort((a, b) => a.localeCompare(b));
  const varNames  = [...parseArrayProp(props.variable_names)].sort((a, b) => a.localeCompare(b));
  const unitNames = [...parseArrayProp(props.unit_names)].sort((a, b) => a.localeCompare(b));

  const toLines = (arr) => arr.length
    ? arr.map((n) => `<div style="padding-left:8px;">${n}</div>`).join('')
    : '<div style="padding-left:8px;">—</div>';

  return `
    <div style="padding:6px 10px;font-size:0.83rem;line-height:1.5;max-height:260px;overflow-y:auto;">
      <div style="font-weight:600;margin-bottom:2px;">${props.name || '—'}</div>
      <div><strong>ID:</strong> ${props.primary_location_id || '—'}</div>
      <div><strong>Configurations:</strong></div>
      ${toLines(cfgNames)}
      <div style="margin-top:4px;"><strong>Variables:</strong></div>
      ${toLines(varNames)}
      <div style="margin-top:4px;"><strong>Units:</strong></div>
      ${toLines(unitNames)}
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

  // Column picker state
  const [activeColumns, setActiveColumns]   = useState(DEFAULT_COLUMNS);
  const [pickerOpen, setPickerOpen]         = useState(false);
  const [checkedKeys, setCheckedKeys]       = useState(new Set());
  const pickerRef                           = useRef(null);

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
    const toAdd = OPTIONAL_COLUMNS.filter(
      (c) => checkedKeys.has(c.key) && !activeColumns.find((a) => a.key === c.key)
    );
    if (toAdd.length === 0) { setPickerOpen(false); return; }
    const newColumns = [...activeColumns, ...toAdd];
    setActiveColumns(newColumns);
    setCheckedKeys(new Set());
    setPickerOpen(false);
    // Re-fetch data with all required fields
    const extraKeys = newColumns
      .filter((c) => !DEFAULT_COLUMNS.find((d) => d.key === c.key))
      .map((c) => c.key);
    setLoading(true);
    setError(null);
    apiService.getConfigurationsByLocationItems({ extra_fields: extraKeys })
      .then((itemsData) => {
        const items = Array.isArray(itemsData)
          ? itemsData
          : Array.isArray(itemsData.items) ? itemsData.items : [];
        setRows(items);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  const handleRemoveColumn = (key) => {
    setActiveColumns((prev) => prev.filter((c) => c.key !== key));
  };

  // Already-added optional keys (to show as added in the picker)
  const addedOptionalKeys = new Set(activeColumns.map((c) => c.key));

  const { sortedRows, handleSort, SortIcon } = useSortableTable(rows, 'primary_location_id', sortValue);

  const [locationIdFilter, setLocationIdFilter]  = useState('');
  const [locationNameFilter, setLocationNameFilter] = useState('');

  const filteredRows = useMemo(() => {
    let result = sortedRows;
    if (locationIdFilter.trim()) {
      const q = locationIdFilter.trim().toLowerCase();
      result = result.filter((row) => String(row.primary_location_id ?? '').toLowerCase().includes(q));
    }
    if (locationNameFilter.trim()) {
      const q = locationNameFilter.trim().toLowerCase();
      result = result.filter((row) => String(row.name ?? '').toLowerCase().includes(q));
    }
    return result;
  }, [sortedRows, locationIdFilter, locationNameFilter]);

  const hasActiveFilter = locationIdFilter || locationNameFilter;

  // Load tabular items only on mount (no geometry fetch)
  const fetchRows = useCallback((extraFields = []) => {
    setLoading(true);
    setError(null);
    apiService.getConfigurationsByLocationItems({ extra_fields: extraFields })
      .then((itemsData) => {
        const items = Array.isArray(itemsData)
          ? itemsData
          : Array.isArray(itemsData.items) ? itemsData.items : [];
        setRows(items);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchRows(); }, [fetchRows]);

  // On row click: fetch geometry from the locations table and full row data from
  // configurations_by_location in parallel, then merge for the map popup.
  const handleRowClick = useCallback((row) => {
    if (selectedId === row.primary_location_id) {
      setSelectedId(null);
      setGeojson(null);
      setBasinGeojson(null);
      setBasinChecked(false);
      setNoGeometry(false);
      return;
    }
    setSelectedId(row.primary_location_id);
    setBasinChecked(false);
    setNoGeometry(false);
    const basinId = row.primary_location_id.replace(/^usgs-/, 'usgsbasin-');
    Promise.all([
      apiService.getLocationById(row.primary_location_id),
      apiService.getConfigurationsByLocationForId(row.primary_location_id),
      apiService.getLocationById(basinId).catch(() => null),
    ])
      .then(([locationData, cblData, basinData]) => {
        const feature = locationData?.features?.[0];
        if (!feature) {
          setNoGeometry(true);
          setBasinChecked(true);
          return;
        }
        const cblRow = Array.isArray(cblData?.items) ? cblData.items[0] : null;
        const merged = {
          type: 'FeatureCollection',
          features: [{
            ...feature,
            properties: {
              ...feature.properties,
              primary_location_id: row.primary_location_id,
              name: cblRow?.name ?? row.name,
              configuration_names: cblRow?.configuration_names ?? row.configuration_names,
              variable_names: cblRow?.variable_names ?? row.variable_names,
              unit_names: cblRow?.unit_names ?? row.unit_names,
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Map — top 1/3 */}
      <div style={{ flex: '1 1 0', minHeight: 0, position: 'relative' }}>
        <SimpleMapPanel
          locations={geojson}
          basinLocations={basinGeojson}
          getPopupHTML={makePopupHTML}
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
                {[...OPTIONAL_COLUMNS].sort((a, b) => a.label.localeCompare(b.label)).map((c) => {
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
          <input
            type="text"
            className="form-control form-control-sm"
            placeholder="Location ID…"
            value={locationIdFilter}
            onChange={(e) => setLocationIdFilter(e.target.value)}
            style={{ width: 150 }}
          />
          <input
            type="text"
            className="form-control form-control-sm"
            placeholder="Location name…"
            value={locationNameFilter}
            onChange={(e) => setLocationNameFilter(e.target.value)}
            style={{ width: 150 }}
          />
          {hasActiveFilter && (
            <button
              className="btn btn-sm btn-outline-secondary"
              onClick={() => { setLocationIdFilter(''); setLocationNameFilter(''); }}
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
                    className={selectedId === row.primary_location_id ? 'table-primary' : ''}
                  >
                    {activeColumns.map((c) => {
                      let val;
                      if (c.key === 'min_value_time' || c.key === 'max_value_time' ||
                          c.key === 'min_reference_time' || c.key === 'max_reference_time') {
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
