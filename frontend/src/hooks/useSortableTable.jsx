import { useState, useMemo } from 'react';

/**
 * useSortableTable
 *
 * Shared sorting logic for data tables across dashboards.
 *
 * @param {Array}    rows          - The raw row array to sort
 * @param {string}   defaultKey    - Column key to sort by initially
 * @param {Function} getSortValue  - Optional fn(row, key) => comparable value.
 *                                   Defaults to numeric-aware string comparison.
 * @returns {{ sortedRows, sortKey, sortDir, handleSort, SortIcon }}
 */
const defaultGetSortValue = (row, key) => {
  const val = row[key];
  if (val == null) return '';
  const num = parseFloat(val);
  return isNaN(num) ? String(val).toLowerCase() : num;
};

export const useSortableTable = (rows, defaultKey = null, getSortValue = null) => {
  const [sortKey, setSortKey] = useState(defaultKey);
  const [sortDir, setSortDir] = useState('asc');

  const resolver = getSortValue ?? defaultGetSortValue;

  const handleSort = (key) => {
    if (key === sortKey) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortedRows = useMemo(() => {
    if (!rows.length || !sortKey) return rows;
    return [...rows].sort((a, b) => {
      const av = resolver(a, sortKey);
      const bv = resolver(b, sortKey);
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ?  1 : -1;
      return 0;
    });
  }, [rows, sortKey, sortDir, resolver]);

  /**
   * Returns a sort indicator element for a given column key.
   * Active column shows ▲ or ▼; inactive columns show a faint ⇅.
   */
  const SortIcon = ({ colKey }) => {
    const active = sortKey === colKey;
    return (
      <span style={{ opacity: active ? 1 : 0.3, fontSize: '0.7rem', marginLeft: '3px' }}>
        {active ? (sortDir === 'asc' ? '▲' : '▼') : '⇅'}
      </span>
    );
  };

  return { sortedRows, sortKey, sortDir, handleSort, SortIcon };
};
