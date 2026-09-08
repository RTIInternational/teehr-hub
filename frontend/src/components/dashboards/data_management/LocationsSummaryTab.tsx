import { useQuery } from '@tanstack/react-query';
import type { FeatureCollection, Point } from 'geojson';
/**
 * LocationsSummaryTab
 *
 * Layout: map panel + table panel
 *
 * Behaviour
 * ---------
 * - Loads tabular rows from locations_with_attributes on mount.
 * - Clicking a table row plots that single location as a point on the map.
 * - Table rows show: location id, name, and various location attributes.
 */
import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { Spinner, Alert } from 'react-bootstrap';

import { attributesOptions } from '@/features/data_management/queries/attributes';
import { useConfigurationsByLocationId } from '@/features/data_management/queries/configurations';
import { useLocationRows } from '@/features/data_management/queries/locationRows';
import type { LocationRow } from '@/features/data_management/types/locationRows';
import { fmt } from '@/features/data_management/utils/utils';
import { formatUnknownValueForDisplay } from '@/shared/utils/formatters';

import { useSortableTable, type SortValueGetter } from '../../../hooks/useSortableTable';
import { apiService } from '../../../services/api';
import DashboardPanel from '../../../shared/components/DashboardPanel';
import SharedDataTable from '../../../shared/components/SharedDataTable';
import SimpleMapPanel, { type PopupFeatureProps } from './SimpleMapPanel';

// ── Helpers ────────────────────────────────────────────────────────────────

// Returns a raw sortable value for a column key
const sortValue: SortValueGetter = (row, key) => {
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
  { key: 'location_id', label: 'Location ID' },
  { key: 'name', label: 'Name' },
  { key: 'state_name', label: 'State' },
  { key: 'drainage_area_km2', label: 'Drainage Area (km²)' },
  { key: 'slope_mean_percent', label: 'Mean Slope (%)' },
  { key: 'rfc', label: 'RFC' },
];

const SIDE_PANEL_COLUMNS = [
  { key: 'configuration_name', label: 'Configuration' },
  { key: 'variable_name', label: 'Variable' },
  { key: 'unit_name', label: 'Unit' },
  { key: 'min_reference_time', label: 'Ref Min' },
  { key: 'max_reference_time', label: 'Ref Max' },
  { key: 'min_value_time', label: 'Val Min' },
  { key: 'max_value_time', label: 'Val Max' },
  { key: 'num_members', label: '# Members' },
];

// Default attribute names fetched from location_attributes on initial load
const DEFAULT_ATTRIBUTE_NAMES = ['state_name', 'drainage_area_km2', 'slope_mean_percent', 'rfc'];

// Popup content for map hover
const makePopupHTML = (props: PopupFeatureProps) => {
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
  const [geojson, setGeojson] = useState<FeatureCollection<Point> | null>(null);
  const [basinGeojson, setBasinGeojson] = useState(null);
  const [noGeometry, setNoGeometry] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [activeColumns, setActiveColumns] = useState(DEFAULT_COLUMNS);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [checkedKeys, setCheckedKeys] = useState(new Set());
  const [filterColumn, setFilterColumn] = useState('');
  const [filterText, setFilterText] = useState('');
  const [pickerMenuStyle, setPickerMenuStyle] = useState({});
  const pickerRef = useRef<HTMLDivElement>(null);

  const attributes = useQuery({
    ...attributesOptions,
    select: (data) => {
      const defaultKeys = new Set(DEFAULT_COLUMNS.map((c) => c.key));
      const attrs = (data?.items || [])
        .filter((item) => !defaultKeys.has(item.name))
        .map((item) => ({ key: item.name, label: item.description || item.name }))
        .sort((a, b) => a.label.localeCompare(b.label));
      return attrs;
    },
  });

  const extraAttributeNames = activeColumns
    .filter((c) => !DEFAULT_COLUMNS.find((d) => d.key === c.key))
    .map((c) => c.key);
  const attributeNames = [...DEFAULT_ATTRIBUTE_NAMES, ...extraAttributeNames];
  const rows = useLocationRows(attributeNames);

  const locationConfigs = useConfigurationsByLocationId(selectedId);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && e.target instanceof Node && !pickerRef.current.contains(e.target))
        setPickerOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (!pickerOpen || !pickerRef.current) {
      return;
    }

    const updatePickerMenuStyle = () => {
      if (!pickerRef.current) return;
      const rect = pickerRef.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
      const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
      const menuWidth = Math.min(340, Math.max(280, viewportWidth - 24));
      const spaceBelow = viewportHeight - rect.bottom - 12;
      const spaceAbove = rect.top - 12;
      const keepOpeningDownward = viewportWidth < 1400 || viewportHeight < 900;
      const openUpward = !keepOpeningDownward && spaceBelow < 260 && spaceAbove > spaceBelow;
      const availableHeight = openUpward ? spaceAbove : spaceBelow;

      setPickerMenuStyle({
        top: openUpward ? 'auto' : '100%',
        bottom: openUpward ? '100%' : 'auto',
        marginTop: openUpward ? 0 : 2,
        marginBottom: openUpward ? 2 : 0,
        width: `${menuWidth}px`,
        maxHeight: `${Math.max(180, Math.min(availableHeight, keepOpeningDownward ? 240 : 360))}px`,
        maxWidth: `calc(100vw - 24px)`,
      });
    };

    updatePickerMenuStyle();
    window.addEventListener('resize', updatePickerMenuStyle);
    window.addEventListener('scroll', updatePickerMenuStyle, true);

    return () => {
      window.removeEventListener('resize', updatePickerMenuStyle);
      window.removeEventListener('scroll', updatePickerMenuStyle, true);
    };
  }, [pickerOpen]);

  const toggleCheck = (key: string) =>
    setCheckedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const handleAddToTable = () => {
    if (checkedKeys.size === 0 || !attributes.data) return;
    const toAdd = attributes.data.filter(
      (c) => checkedKeys.has(c.key) && !activeColumns.find((a) => a.key === c.key)
    );
    if (toAdd.length === 0) {
      setPickerOpen(false);
      return;
    }
    const newColumns = [...activeColumns, ...toAdd];
    setActiveColumns(newColumns);
    setCheckedKeys(new Set());
    setPickerOpen(false);
  };

  const handleRemoveColumn = (key: string) => {
    setActiveColumns((prev) => prev.filter((c) => c.key !== key));
  };

  const addedOptionalKeys = new Set(activeColumns.map((c) => c.key));
  const { sortedRows, handleSort, SortIcon } = useSortableTable(
    rows.data ?? [],
    'location_id',
    sortValue
  );
  const {
    sortedRows: sortedSidePanelConfigs,
    handleSort: handleSidePanelSort,
    SortIcon: SidePanelSortIcon,
  } = useSortableTable(locationConfigs.data ?? [], 'configuration_name', sortValue);

  const selectedLocationRow = useMemo(
    () => rows.data?.find((row) => row.location_id === selectedId) ?? null,
    [rows.data, selectedId]
  );

  const filteredRows = useMemo(() => {
    if (!filterText.trim()) return sortedRows;
    const q = filterText.trim().toLowerCase();
    if (filterColumn) {
      return sortedRows.filter((row) =>
        String(row[filterColumn] ?? '')
          .toLowerCase()
          .includes(q)
      );
    }
    return sortedRows.filter((row) =>
      activeColumns.some((col) =>
        String(row[col.key] ?? '')
          .toLowerCase()
          .includes(q)
      )
    );
  }, [sortedRows, filterText, filterColumn, activeColumns]);

  const hasActiveFilter = !!filterText;

  const handleRowClick = useCallback(
    (row: LocationRow) => {
      if (selectedId === row.location_id) {
        setSelectedId(null);
        setGeojson(null);
        setBasinGeojson(null);
        setNoGeometry(false);
        return;
      }

      setSelectedId(row.location_id);
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
            return;
          }
          const merged: FeatureCollection<Point> = {
            type: 'FeatureCollection',
            features: [
              {
                ...feature,
                properties: {
                  ...feature.properties,
                  location_id: row.location_id,
                  name: row.name,
                },
              },
            ],
          };
          setGeojson(merged);
          const hasBasin = !!basinData?.features?.length;
          setBasinGeojson(hasBasin ? basinData : null);
        })
        .catch(() => {
          setNoGeometry(true);
        });
    },
    [selectedId]
  );

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        minHeight: 0,
        gap: '12px',
      }}
    >
      <div style={{ flex: '1 1 0', minHeight: 0, display: 'flex', gap: '12px' }}>
        <div style={{ flex: '1 1 0', minWidth: 0, minHeight: 0, position: 'relative' }}>
          <DashboardPanel bodyStyle={{ padding: 0, position: 'relative' }}>
            <SimpleMapPanel
              locations={geojson}
              basinLocations={basinGeojson}
              getPopupHTML={makePopupHTML}
              isActive={isActive}
            />
            {!selectedId && (
              <div
                className="position-absolute top-50 start-50 translate-middle text-center text-muted"
                style={{
                  zIndex: 5,
                  pointerEvents: 'none',
                  background: 'rgba(255,255,255,0.7)',
                  borderRadius: 6,
                  padding: '6px 12px',
                }}
              >
                <small>Click a location row below to view it on the map</small>
              </div>
            )}
            {selectedId && noGeometry && (
              <div
                className="position-absolute top-50 start-50 translate-middle text-center text-muted"
                style={{
                  zIndex: 5,
                  pointerEvents: 'none',
                  background: 'rgba(255,255,255,0.82)',
                  borderRadius: 6,
                  padding: '6px 12px',
                }}
              >
                <small>
                  <i className="bi bi-exclamation-circle me-1" />
                  No geometry found for this location
                </small>
              </div>
            )}
          </DashboardPanel>
        </div>

        <div style={{ flex: '0 0 50%', minWidth: 0, minHeight: 0 }}>
          <DashboardPanel
            header={
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <strong style={{ fontSize: '0.9rem' }}>Configurations</strong>
                {selectedLocationRow ? (
                  <div style={{ fontSize: '0.78rem', color: '#6c757d', lineHeight: 1.3 }}>
                    <span>{selectedLocationRow.name || 'Unnamed location'}</span>
                    <span className="mx-1">•</span>
                    <span>{selectedLocationRow.location_id}</span>
                  </div>
                ) : (
                  <div style={{ fontSize: '0.78rem', color: '#6c757d', lineHeight: 1.3 }}>
                    Select a location from the table below.
                  </div>
                )}
              </div>
            }
            bodyStyle={{ padding: 0 }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
              {!selectedId ? (
                <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
                  <div className="text-center">
                    <div style={{ fontSize: '3rem' }}>📍</div>
                    <h5>Select a Location</h5>
                    <p>Click a location row below to view its configurations.</p>
                  </div>
                </div>
              ) : locationConfigs.isLoading ? (
                <div className="d-flex align-items-center justify-content-center flex-grow-1">
                  <div className="text-center">
                    <Spinner animation="border" variant="primary" />
                    <div className="mt-2 small text-muted">Loading configurations...</div>
                  </div>
                </div>
              ) : locationConfigs.error ? (
                <Alert variant="danger" className="m-3">
                  <i className="bi bi-exclamation-triangle-fill me-2" />
                  {locationConfigs.error.message}
                </Alert>
              ) : locationConfigs.data && locationConfigs.data.length > 0 ? (
                <SharedDataTable
                  headers={SIDE_PANEL_COLUMNS}
                  rows={sortedSidePanelConfigs}
                  wrapperStyle={{ flex: '1 1 0', minHeight: 0, overflowY: 'auto' }}
                  tableClassName="table table-sm table-bordered table-hover mb-0"
                  tableStyle={{ fontSize: '0.82rem' }}
                  getHeaderKey={(column) => column.key}
                  renderHeaderCell={(column) => (
                    <>
                      {column.label}
                      <SidePanelSortIcon colKey={column.key} />
                    </>
                  )}
                  getHeaderProps={(column) => ({
                    onClick: () => handleSidePanelSort(column.key),
                    style: {
                      whiteSpace: 'nowrap',
                      verticalAlign: 'middle',
                      cursor: 'pointer',
                      userSelect: 'none',
                    },
                    title: `Sort by ${column.label}`,
                  })}
                  renderCell={(row, column) => {
                    const raw = row[column.key];
                    const isDateField =
                      column.key === 'min_reference_time' ||
                      column.key === 'max_reference_time' ||
                      column.key === 'min_value_time' ||
                      column.key === 'max_value_time';
                    if (isDateField && (typeof raw === 'string' || typeof raw === 'number')) {
                      return fmt(raw);
                    }
                    return formatUnknownValueForDisplay(raw, { nullishText: '—' });
                  }}
                  getCellProps={(row, column) => {
                    const value = row[column.key] ?? '—';
                    if (
                      column.key === 'configuration_name' ||
                      column.key === 'variable_name' ||
                      column.key === 'unit_name'
                    ) {
                      return { title: formatUnknownValueForDisplay(value) };
                    }
                    return {};
                  }}
                />
              ) : (
                <div className="d-flex align-items-center justify-content-center flex-grow-1 text-muted">
                  <div className="text-center">
                    <div style={{ fontSize: '2rem' }}>🗂️</div>
                    <h6 className="mb-1">No Configurations</h6>
                    <p className="small mb-0">This location does not have any configurations.</p>
                  </div>
                </div>
              )}
            </div>
          </DashboardPanel>
        </div>
      </div>

      <div style={{ flex: '1 1 0', minHeight: 0 }}>
        <DashboardPanel
          header={
            <div
              ref={pickerRef}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                flexWrap: 'wrap',
                position: 'relative',
              }}
            >
              <button
                className="btn btn-sm btn-outline-secondary"
                style={{ fontSize: '0.8rem' }}
                onClick={() => setPickerOpen((o) => !o)}
              >
                <i className="bi bi-columns-gap me-1" />
                Add columns {pickerOpen ? '▲' : '▼'}
              </button>
              {activeColumns
                .filter((c) => !DEFAULT_COLUMNS.find((d) => d.key === c.key))
                .map((c) => (
                  <span
                    key={c.key}
                    className="badge bg-primary d-flex align-items-center"
                    style={{ fontSize: '0.75rem', gap: 4 }}
                  >
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
                    width: 'min(340px, calc(100vw - 24px))',
                    maxHeight: 'min(360px, calc(100dvh - 24px))',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                    ...pickerMenuStyle,
                  }}
                >
                  <div
                    style={{
                      padding: '6px 10px',
                      borderBottom: '1px solid #dee2e6',
                      fontWeight: 600,
                      fontSize: '0.82rem',
                    }}
                  >
                    Select columns to add
                  </div>
                  <div
                    style={{ overflowY: 'auto', flex: '1 1 auto', minHeight: 0, padding: '4px 0' }}
                  >
                    {attributes.data &&
                      attributes.data.map((c) => {
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
                            {alreadyAdded && (
                              <span style={{ fontSize: '0.72rem', color: '#aaa' }}>(added)</span>
                            )}
                          </label>
                        );
                      })}
                  </div>
                  <div
                    style={{
                      padding: '6px 10px',
                      borderTop: '1px solid #dee2e6',
                      display: 'flex',
                      justifyContent: 'flex-end',
                      gap: 6,
                      flexWrap: 'wrap',
                    }}
                  >
                    <button
                      className="btn btn-sm btn-outline-secondary"
                      onClick={() => {
                        setCheckedKeys(new Set());
                        setPickerOpen(false);
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      className="btn btn-sm btn-primary"
                      onClick={handleAddToTable}
                      disabled={checkedKeys.size === 0}
                    >
                      Add to table
                    </button>
                  </div>
                </div>
              )}

              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#495057' }}>Filter:</span>
              <select
                className="form-select form-select-sm"
                value={filterColumn}
                onChange={(e) => {
                  setFilterColumn(e.target.value);
                  setFilterText('');
                }}
                style={{ width: 160 }}
              >
                <option value="">— All columns —</option>
                {activeColumns.map((col) => (
                  <option key={col.key} value={col.key}>
                    {col.label}
                  </option>
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
                  onClick={() => {
                    setFilterText('');
                    setFilterColumn('');
                  }}
                  style={{ fontSize: '0.8rem' }}
                >
                  Clear
                </button>
              )}
              {rows.data && rows.data.length > 0 && (
                <span className="text-muted ms-auto" style={{ fontSize: '0.78rem' }}>
                  {filteredRows.length} / {rows.data.length} rows
                </span>
              )}
            </div>
          }
          bodyStyle={{ padding: 0 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            {rows.isLoading && (
              <div className="d-flex align-items-center justify-content-center h-100">
                <Spinner animation="border" variant="primary">
                  <span className="visually-hidden">Loading locations…</span>
                </Spinner>
              </div>
            )}

            {rows.error && (
              <Alert variant="danger" className="m-3 mb-0">
                <i className="bi bi-exclamation-triangle-fill me-2" />
                {rows.error.message}
              </Alert>
            )}

            {!rows.isLoading && !rows.error && (!rows.data || rows.data.length === 0) && (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <span>No locations available.</span>
              </div>
            )}

            {!rows.isLoading && !rows.error && rows.data && rows.data.length > 0 && (
              <SharedDataTable
                headers={activeColumns}
                rows={filteredRows}
                wrapperStyle={{ overflowX: 'auto', overflowY: 'auto', flex: 1 }}
                getHeaderKey={(column) => column.key}
                renderHeaderCell={(column) => (
                  <>
                    {column.label}
                    <SortIcon colKey={column.key} />
                  </>
                )}
                getHeaderProps={(column) => ({
                  onClick: () => handleSort(column.key),
                  style: {
                    whiteSpace: 'nowrap',
                    verticalAlign: 'middle',
                    cursor: 'pointer',
                    userSelect: 'none',
                  },
                  title: `Sort by ${column.label}`,
                })}
                getRowProps={(row) => ({
                  onClick: () => handleRowClick(row),
                  style: { cursor: 'pointer' },
                  className: selectedId === row.location_id ? 'table-primary' : '',
                })}
                renderCell={(row, column) => {
                  if (column.key === 'min_reference_time' || column.key === 'max_reference_time') {
                    return String(fmt(row[column.key]));
                  }
                  return String(row[column.key] ?? '—');
                }}
                getCellProps={(row, column) => {
                  const value =
                    column.key === 'min_reference_time' || column.key === 'max_reference_time'
                      ? fmt(row[column.key])
                      : (row[column.key] ?? '—');
                  return {
                    style: {
                      verticalAlign: 'middle',
                      maxWidth: 280,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    },
                    title: String(value),
                  };
                }}
              />
            )}
          </div>
        </DashboardPanel>
      </div>
    </div>
  );
};

export default LocationsSummaryTab;
