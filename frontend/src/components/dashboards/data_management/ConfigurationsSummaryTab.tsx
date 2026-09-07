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
import { useState, useCallback, useMemo } from 'react';
import { Spinner, Alert } from 'react-bootstrap';

import {
  useConfigurationsLocationsGeoJson,
  useConfigurationsTable,
} from '@/features/data_management/queries/configurations';
import type { ConfigurationsTableItem } from '@/features/data_management/types/configurations';
import { displayUnknown } from '@/shared/utils/formatters';

import { useSortableTable, type SortValueGetter } from '../../../hooks/useSortableTable';
import DashboardPanel from '../../../shared/components/DashboardPanel';
import SharedDataTable from '../../../shared/components/SharedDataTable';
import SimpleMapPanel, { type PopupFeatureProps } from './SimpleMapPanel';

// ── Helpers ────────────────────────────────────────────────────────────────
const fmt = (val: string | number) => {
  if (val == null) return '—';
  return String(val)
    .replace('T', ' ')
    .replace(/\.\d+Z?$/, '');
};

// Returns a raw sortable value for a column key
const sortValue: SortValueGetter = (row, key) => {
  if (key === 'n_locations') return row.n_locations ?? 0;
  return String(row[key] ?? '').toLowerCase();
};

const DATE_TIME_FIELDS = [
  'min_value_time',
  'max_value_time',
  'min_reference_time',
  'max_reference_time',
];

const compareRows = (r1: ConfigurationsTableItem | null, r2: ConfigurationsTableItem | null) => {
  const str1 = JSON.stringify(r1);
  const str2 = JSON.stringify(r2);
  if (str1 === str2) return true;
  return false;
};

// ── Component ──────────────────────────────────────────────────────────────
const COLUMNS = [
  { key: 'configuration_name', label: 'Configuration' },
  { key: 'variable_name', label: 'Variable' },
  { key: 'n_locations', label: '# Locations' },
  { key: 'unit_name', label: 'Unit' },
  { key: 'timeseries_type', label: 'Type' },
  { key: 'min_value_time', label: 'Value Time Min' },
  { key: 'max_value_time', label: 'Value Time Max' },
  { key: 'min_reference_time', label: 'Reference Time Min' },
  { key: 'max_reference_time', label: 'Reference Time Max' },
  { key: 'description', label: 'Description' },
];

// Popup HTML for locations belonging to selected config
const makePopupHTML = (props: PopupFeatureProps) => `
  <div style="padding:6px 10px;font-size:0.83rem;line-height:1.4;">
    <div style="font-weight:600;margin-bottom:2px;">${props.name || props.primary_location_id || ''}</div>
    <div><strong>ID:</strong> ${props.primary_location_id || '—'}</div>
  </div>
`;

const ConfigurationsSummaryTab = ({ isActive = true }) => {
  const [selectedRow, setSelectedRow] = useState<ConfigurationsTableItem | null>(null);

  // Load summary table on mount
  const configTable = useConfigurationsTable();
  const rows = configTable.data ?? [];

  const mapLocations = useConfigurationsLocationsGeoJson(
    selectedRow?.configuration_name,
    selectedRow?.variable_name
  );

  const { sortedRows, handleSort, SortIcon } = useSortableTable(
    rows,
    'configuration_name',
    sortValue
  );

  const [filterText, setFilterText] = useState('');

  const filteredRows = useMemo(() => {
    if (!filterText.trim()) return sortedRows;
    const q = filterText.trim().toLowerCase();
    return sortedRows.filter((row) => row.configuration_name.toLowerCase().includes(q));
  }, [sortedRows, filterText]);

  // Fetch locations for the clicked row
  const handleRowClick = useCallback(
    async (row: ConfigurationsTableItem) => {
      if (compareRows(selectedRow, row)) {
        setSelectedRow(null);
        return;
      }
      setSelectedRow(row);
    },
    [selectedRow]
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
      <div style={{ flex: '1 1 0', minHeight: 0 }}>
        <DashboardPanel bodyStyle={{ padding: 0, position: 'relative' }}>
          <SimpleMapPanel
            locations={mapLocations.data}
            getPopupHTML={makePopupHTML}
            isActive={isActive}
          />
          {mapLocations.isLoading && (
            <div
              className="position-absolute top-50 start-50 translate-middle text-center"
              style={{ zIndex: 10 }}
            >
              <output className="spinner-border spinner-border-sm text-primary" />
              <div className="small text-muted mt-1">Loading locations…</div>
            </div>
          )}
          {!selectedRow && !mapLocations.isLoading && (
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
              <small>Click a configuration row below to view its locations</small>
            </div>
          )}
        </DashboardPanel>
      </div>

      <div style={{ flex: '1.3 1 0', minHeight: 0 }}>
        <DashboardPanel
          header={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#495057' }}>Filter:</span>
              <input
                type="text"
                className="form-control form-control-sm"
                placeholder="Configuration name…"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                style={{ width: 220 }}
              />
              {filterText && (
                <button
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => setFilterText('')}
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
          }
          bodyStyle={{ padding: 0 }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            {configTable.isLoading && (
              <div className="d-flex align-items-center justify-content-center h-100">
                <Spinner animation="border" variant="primary">
                  <span className="visually-hidden">Loading configurations…</span>
                </Spinner>
              </div>
            )}

            {configTable.error && (
              <Alert variant="danger" className="m-3 mb-0">
                <i className="bi bi-exclamation-triangle-fill me-2" />
                {configTable.error.message}
              </Alert>
            )}

            {!configTable.isLoading && !configTable.error && rows.length === 0 && (
              <div className="d-flex align-items-center justify-content-center h-100 text-muted">
                <span>No configurations available.</span>
              </div>
            )}

            {!configTable.isLoading && !configTable.error && rows.length > 0 && (
              <SharedDataTable
                headers={COLUMNS}
                rows={filteredRows}
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
                getRowProps={(row) => {
                  const isSelected = compareRows(selectedRow, row);
                  return {
                    onClick: () => handleRowClick(row),
                    style: { cursor: 'pointer', background: isSelected ? '#cfe2ff' : undefined },
                    className: isSelected ? 'table-primary' : '',
                  };
                }}
                renderCell={(row, column) => {
                  const isSelected = compareRows(selectedRow, row);
                  const rawVal = row[column.key];
                  const value =
                    DATE_TIME_FIELDS.includes(column.key) &&
                    (typeof rawVal === 'string' || typeof rawVal === 'number')
                      ? fmt(rawVal)
                      : (rawVal ?? '—');

                  return column.key === 'configuration_name' && isSelected ? (
                    <strong>{value as string}</strong>
                  ) : (
                    displayUnknown(value)
                  );
                }}
                getCellProps={(row, column) => {
                  const rawVal = row[column.key];
                  const value =
                    DATE_TIME_FIELDS.includes(column.key) &&
                    (typeof rawVal === 'string' || typeof rawVal === 'number')
                      ? fmt(rawVal)
                      : (rawVal ?? '—');
                  return {
                    style: {
                      verticalAlign: 'middle',
                      maxWidth: 260,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    },
                    title: displayUnknown(value),
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

export default ConfigurationsSummaryTab;
