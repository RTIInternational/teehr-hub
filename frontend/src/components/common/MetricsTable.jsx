import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Duration } from 'luxon';
import Plotly from 'plotly.js-dist-min';
import { Button, ButtonGroup } from 'react-bootstrap';
import './MetricsTable.css';

const MetricsTable = ({ 
  metrics = [], 
  loading = false, 
  error = null,
  title = "Metrics",
  emptyMessage = "No metrics available for this location.",
  showTitle = true,
  tableProperties = null, // Contains group_by and metrics info for pivoting
  viewMode = 'table', // Allow external control
  onViewModeChange = null // Callback for view mode changes
}) => {
  const [internalViewMode, setInternalViewMode] = useState('table');
  const currentViewMode = onViewModeChange ? viewMode : internalViewMode;
  const setCurrentViewMode = onViewModeChange ? onViewModeChange : setInternalViewMode;
  
  const plotRef = useRef(null);
  const [sortConfig, setSortConfig] = useState({ column: null, direction: 'asc' });
  const [filters, setFilters] = useState({});
  const [dropdownOpen, setDropdownOpen] = useState({});
  
  // Function to parse duration for sorting
  const parseDurationForSort = (durationStr) => {
    if (!durationStr || typeof durationStr !== 'string') return 0;
    
    // Handle BINSTART_BINEND format - use start time for sorting
    let duration = durationStr;
    if (durationStr.includes('_')) {
      duration = durationStr.split('_')[0];
    }
    
    try {
      const dur = Duration.fromISO(duration);
      return dur.isValid ? dur.as('milliseconds') : 0;
    } catch {
      return 0;
    }
  };
  
  // Function to format lead time bin values using Luxon
  const formatLeadTimeBin = (value) => {
    if (!value || typeof value !== 'string') return value;
    
    // Check if it matches the BINSTART_BINEND pattern
    if (value.includes('_') && (value.startsWith('P') || value.includes('PT'))) {
      try {
        const [startDuration, endDuration] = value.split('_');
        
        // Parse ISO8601 durations with Luxon
        const startDur = Duration.fromISO(startDuration);
        const endDur = Duration.fromISO(endDuration);
        
        if (!startDur.isValid || !endDur.isValid) {
          return value; // Fallback to original if parsing fails
        }
        
        // Format durations in human readable form
        const startText = startDur.as('milliseconds') === 0 ? '0' : 
          startDur.toHuman({ maximumFractionDigits: 0 });
        const endText = endDur.toHuman({ maximumFractionDigits: 0 });
        
        return `${startText} - ${endText}`;
      } catch (error) {
        console.warn('Failed to parse lead time bin:', value, error);
        return value; // Fallback to original value
      }
    }
    
    return value;
  };
  
  // Function to format cell values based on field name and content
  const formatCellValue = (header, value) => {
    if (value === null || value === undefined) return 'N/A';
    
    // Special formatting for lead time bin fields
    if (header.toLowerCase().includes('lead_time_bin') || 
        header.toLowerCase().includes('forecast_lead_time_bin')) {
      return formatLeadTimeBin(value);
    }
    
    // Format numbers
    if (typeof value === 'number') {
      return value.toFixed(4);
    }
    
    return value;
  };
  
  // Sorting function
  const handleSort = (columnIndex, header) => {
    let direction = 'asc';
    if (sortConfig.column === columnIndex && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ column: columnIndex, direction });
  };
  
  // Filter function for text inputs (fallback)
  const handleFilterChange = (columnIndex, value) => {
    setFilters(prev => ({
      ...prev,
      [columnIndex]: value
    }));
  };
  
  // Checkbox filter function for group_by columns
  const handleCheckboxFilterChange = (columnIndex, value, checked) => {
    setFilters(prev => {
      const currentFilter = prev[columnIndex] || [];
      if (checked) {
        return {
          ...prev,
          [columnIndex]: [...currentFilter, value]
        };
      } else {
        return {
          ...prev,
          [columnIndex]: currentFilter.filter(v => v !== value)
        };
      }
    });
  };

  // Clear all filters
  const clearFilters = () => {
    setFilters({});
  };
  
  // Toggle dropdown visibility
  const toggleDropdown = (columnIndex) => {
    setDropdownOpen(prev => ({
      ...prev,
      [columnIndex]: !prev[columnIndex]
    }));
  };
  
  // Function to sort rows
  const sortRows = (rowsToSort, headers) => {
    if (sortConfig.column === null) return rowsToSort;
    
    return [...rowsToSort].sort((a, b) => {
      const aVal = a[sortConfig.column];
      const bVal = b[sortConfig.column];
      
      // Handle numeric values
      const aNum = parseFloat(aVal);
      const bNum = parseFloat(bVal);
      
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortConfig.direction === 'asc' ? aNum - bNum : bNum - aNum;
      }
      
      // Handle string values
      const aStr = String(aVal).toLowerCase();
      const bStr = String(bVal).toLowerCase();
      
      if (aStr < bStr) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aStr > bStr) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
  };
  
  // Function to filter rows
  const filterRows = (rowsToFilter) => {
    return rowsToFilter.filter(row => {
      return Object.entries(filters).every(([columnIndex, filterValue]) => {
        if (!filterValue || (Array.isArray(filterValue) && filterValue.length === 0)) return true;
        
        const cellValue = String(row[parseInt(columnIndex)]);
        
        // Handle checkbox-based filters (arrays)
        if (Array.isArray(filterValue)) {
          return filterValue.includes(cellValue);
        }
        
        // Handle text-based filters (fallback)
        return cellValue.toLowerCase().includes(filterValue.toLowerCase());
      });
    });
  };
  
  // Function to pivot the data based on table properties
  const { headers, rows: rawRows, hasLeadTimeBin } = useMemo(() => {
    if (!tableProperties?.group_by || !tableProperties?.metrics || !Array.isArray(metrics)) {
      
      // Fallback to simple key-value pairs if no table properties
      if (Array.isArray(metrics) && metrics.length > 0) {
        // If it's already in metric_name/metric_value format (fallback)
        if (metrics[0].metric_name && metrics[0].metric_value !== undefined) {
          return { headers: ['Metric', 'Value'], rows: metrics.map(m => [m.metric_name || 'Unknown', m.metric_value]), hasLeadTimeBin: false };
        }
        // If it's raw properties, show first object's key-value pairs
        const firstItem = metrics[0];
        const entries = Object.entries(firstItem).filter(([key, value]) => value !== null && value !== undefined);
        return { headers: ['Field', 'Value'], rows: entries.map(([key, value]) => [key, formatCellValue(key, value)]), hasLeadTimeBin: false };
      }
      return { headers: ['Field', 'Value'], rows: [], hasLeadTimeBin: false };
    }
    
    const groupByFields = tableProperties.group_by;
    const metricFields = tableProperties.metrics;
    
    // Check if we have a lead time bin column
    const leadTimeBinField = groupByFields.find(field => 
      field.toLowerCase().includes('lead_time_bin') || 
      field.toLowerCase().includes('forecast_lead_time_bin') ||
      field.toLowerCase().includes('leadtimebin') ||
      field.toLowerCase().includes('lead_time') ||
      field.toLowerCase().includes('bin')
    );
    const hasLeadTimeBin = !!leadTimeBinField;
    
    // Debug: log the first data item to see available fields
    // Sort data by lead time bin if present
    let sortedMetrics = [...metrics];
    if (hasLeadTimeBin && leadTimeBinField) {
      sortedMetrics.sort((a, b) => {
        const aValue = parseDurationForSort(a[leadTimeBinField]);
        const bValue = parseDurationForSort(b[leadTimeBinField]);
        return aValue - bValue;
      });
    }
    
    // No need to group - each row in metrics array is already a complete row
    const headers = [...groupByFields, ...metricFields];
    
    // Build rows directly from the sorted data
    const rows = sortedMetrics.map(item => {
      return headers.map(header => {
        const value = item[header];
        return formatCellValue(header, value);
      });
    });
    
    return { headers, rows, hasLeadTimeBin };
  }, [metrics, tableProperties]);
  
  // Compute unique values for all group_by columns
  const uniqueValuesByColumn = useMemo(() => {
    if (!rawRows || rawRows.length === 0 || !tableProperties?.group_by) return {};
    
    const uniqueValues = {};
    const groupByLength = tableProperties.group_by.length;
    
    try {
      for (let columnIndex = 0; columnIndex < groupByLength; columnIndex++) {
        const values = rawRows.map(row => {
          const value = row && row[columnIndex] !== undefined ? row[columnIndex] : '';
          return String(value);
        });
        uniqueValues[columnIndex] = [...new Set(values)].sort();
      }
    } catch (error) {
      console.error('Error computing unique values:', error);
      return {};
    }
    
    return uniqueValues;
  }, [rawRows, tableProperties?.group_by]);

  // Apply filtering and sorting
  const processedRows = useMemo(() => {
    let filteredRows = filterRows(rawRows);
    let sortedRows = sortRows(filteredRows, headers);
    return sortedRows;
  }, [rawRows, headers, filters, sortConfig]);
  
  // Prepare data for plotting
  const plotData = useMemo(() => {
    if (!hasLeadTimeBin || !tableProperties?.group_by || !tableProperties?.metrics || !processedRows || processedRows.length === 0) {
      return [];
    }
    
    const groupByFields = tableProperties.group_by;
    const metricFields = tableProperties.metrics;
    const leadTimeBinField = groupByFields.find(field => 
      field.toLowerCase().includes('lead_time_bin') || 
      field.toLowerCase().includes('forecast_lead_time_bin')
    );
    
    if (!leadTimeBinField) return [];
    
    const leadTimeBinIndex = headers.indexOf(leadTimeBinField);
    if (leadTimeBinIndex === -1) return [];
    
    // Get non-lead-time group_by columns for grouping traces
    const nonLeadTimeGroupByFields = groupByFields.filter(field => 
      !field.toLowerCase().includes('lead_time_bin') && 
      !field.toLowerCase().includes('forecast_lead_time_bin')
    );
    
    // Convert filtered table rows back to objects for plotting
    const filteredData = processedRows.map(row => {
      const item = {};
      headers.forEach((header, index) => {
        item[header] = row[index];
      });
      return item;
    });
    
    // Check which non-lead-time columns have more than one unique value
    const relevantGroupByFields = nonLeadTimeGroupByFields.filter(field => {
      const uniqueValues = new Set(filteredData.map(item => item[field]));
      return uniqueValues.size > 1;
    });
    
    // Group data by relevant non-lead-time columns (only those with multiple values)
    const groupedData = {};
    filteredData.forEach(item => {
      // Create a key from relevant group_by values only
      const groupKey = relevantGroupByFields.length > 0 
        ? relevantGroupByFields.map(field => `${field}: ${item[field]}`).join(', ')
        : 'All Data';
      
      if (!groupedData[groupKey]) {
        groupedData[groupKey] = [];
      }
      groupedData[groupKey].push(item);
    });
    
    // Create traces for each group and each metric
    const traces = [];
    
    Object.entries(groupedData).forEach(([groupKey, groupData]) => {
      // Sort group data by lead time bin for proper x-axis ordering
      const sortedGroupData = [...groupData].sort((a, b) => {
        const aValue = parseDurationForSort(a[leadTimeBinField]);
        const bValue = parseDurationForSort(b[leadTimeBinField]);
        return aValue - bValue;
      });
      
      metricFields.forEach(metric => {
        const xValues = sortedGroupData.map(item => formatCellValue(leadTimeBinField, item[leadTimeBinField]));
        const yValues = sortedGroupData.map(item => {
          const value = item[metric];
          return typeof value === 'string' ? parseFloat(value) : value;
        });
        
        // Create trace name combining group and metric (only for relevant columns)
        const traceName = relevantGroupByFields.length > 0 
          ? `${metric} (${groupKey})`
          : metric;
        
        traces.push({
          x: xValues,
          y: yValues,
          type: 'scatter',
          mode: 'lines+markers',
          name: traceName,
          line: { width: 2 },
          marker: { size: 6 },
          // Add hover info showing the relevant group values only
          hovertemplate: relevantGroupByFields.length > 0 
            ? `${metric}<br>${groupKey}<br>Lead Time: %{x}<br>Value: %{y}<extra></extra>`
            : `${metric}<br>Lead Time: %{x}<br>Value: %{y}<extra></extra>`
        });
      });
    });
    
    return traces;
  }, [processedRows, headers, tableProperties, hasLeadTimeBin]);
  
  // Effect to render plot when in plot mode
  useEffect(() => {
    if (currentViewMode === 'plot' && hasLeadTimeBin && plotRef.current && plotData.length > 0) {
      const layout = {
        title: 'Metrics by Lead Time Bin',
        xaxis: { 
          title: 'Lead Time Bin',
          type: 'category'
        },
        yaxis: { 
          title: 'Metric Value'
        },
        margin: { l: 50, r: 50, t: 50, b: 100 },
        showlegend: true,
        legend: {
          x: 1,
          xanchor: 'left',
          y: 1
        }
      };
      
      Plotly.react(plotRef.current, plotData, layout, {
        displayModeBar: true,
        modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
        responsive: true
      });
    } else if (currentViewMode === 'table' && plotRef.current) {
      // Clear the plot when switching to table mode
      Plotly.purge(plotRef.current);
    }
  }, [currentViewMode, hasLeadTimeBin, plotData]);
  
  if (loading) {
    return (
      <div className="metrics-table-container">
        {showTitle && (
          <div className="metrics-table-header">
            <h3>{title}</h3>
          </div>
        )}
        <div className="metrics-table-loading">
          <div className="loading-spinner"></div>
          <span>Loading metrics...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="metrics-table-container">
        {showTitle && (
          <div className="metrics-table-header">
            <h3>{title}</h3>
          </div>
        )}
        <div className="metrics-table-error">
          <span>Error loading metrics: {error}</span>
        </div>
      </div>
    );
  }

  if (!metrics || rawRows.length === 0) {
    return (
      <div className="metrics-table-container">
        {showTitle && (
          <div className="metrics-table-header">
            <h3>{title}</h3>
          </div>
        )}
        <div className="metrics-table-empty">
          <span>{emptyMessage}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="metrics-table-container">
      {showTitle && (
        <div className="metrics-table-header">
          <h3>{title}</h3>
          <div className="d-flex align-items-center gap-2">
            <span className="metrics-count">({processedRows.length} rows{Object.values(filters).some(f => Array.isArray(f) ? f.length > 0 : f) ? ` of ${rawRows.length}` : ''})</span>
          </div>
        </div>
      )}
      
      {/* Toggle buttons when showTitle is false but hasLeadTimeBin is true and NOT externally controlled */}
      {!showTitle && hasLeadTimeBin && !onViewModeChange && (
        <div className="metrics-toggle-header" style={{ 
          padding: '8px 12px', 
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: '#f8f9fa'
        }}>
          <ButtonGroup size="sm">
            <Button 
              variant={currentViewMode === 'table' ? 'primary' : 'outline-primary'}
              onClick={() => setCurrentViewMode('table')}
            >
              📊 Table
            </Button>
            <Button 
              variant={currentViewMode === 'plot' ? 'primary' : 'outline-primary'}
              onClick={() => setCurrentViewMode('plot')}
            >
              📈 Plot
            </Button>
          </ButtonGroup>
          <span className="metrics-count small text-muted">({processedRows.length} rows{Object.values(filters).some(f => Array.isArray(f) ? f.length > 0 : f) ? ` of ${rawRows.length}` : ''})</span>
        </div>
      )}
      
      {currentViewMode === 'plot' && hasLeadTimeBin ? (
        <div key="plot-view" className="metrics-plot-container" style={{ height: '400px', padding: '10px' }}>
          <div ref={plotRef} style={{ width: '100%', height: '100%' }} />
        </div>
      ) : (
        <div key="table-view" className="metrics-table-wrapper" style={{ overflowX: 'auto' }}>
          {/* Filter controls */}
          {Object.keys(filters).length > 0 && Object.values(filters).some(f => Array.isArray(f) ? f.length > 0 : f) && (
            <div className="filter-controls" style={{ 
              padding: '8px 12px', 
              backgroundColor: '#f8f9fa', 
              borderBottom: '1px solid #e0e0e0',
              fontSize: '12px'
            }}>
              <span className="text-muted">
                Active filters: {Object.entries(filters).filter(([_, f]) => Array.isArray(f) ? f.length > 0 : f).length}
              </span>
              <button 
                className="btn btn-sm btn-outline-secondary ms-2"
                onClick={clearFilters}
                style={{ fontSize: '11px', padding: '2px 8px' }}
              >
                Clear All
              </button>
            </div>
          )}
          
          <table className="metrics-table pivoted-table">
            <thead>
              <tr>
                {headers.map((header, index) => {
                  const isGroupByColumn = index < (tableProperties?.group_by?.length || 0);
                  const uniqueValues = isGroupByColumn ? (uniqueValuesByColumn[index] || []) : [];
                  const selectedValues = filters[index] || [];
                  
                  return (
                    <th key={index} 
                        className={isGroupByColumn ? 'group-by-header' : 'metric-header'}
                        style={{ position: 'relative', minWidth: '120px' }}
                    >
                      <div 
                        className="sortable-header"
                        onClick={() => handleSort(index, header)}
                        style={{ 
                          cursor: 'pointer', 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'space-between',
                          userSelect: 'none'
                        }}
                      >
                        <span>{header}</span>
                        <span className="sort-indicator">
                          {sortConfig.column === index && (
                            sortConfig.direction === 'asc' ? '▲' : '▼'
                          )}
                        </span>
                      </div>
                      
                      {/* Only show filters for group_by columns */}
                      {isGroupByColumn && (
                        <div className="position-relative mt-1">
                          <button
                            className="btn btn-sm btn-outline-secondary w-100 d-flex justify-content-between align-items-center"
                            type="button"
                            style={{ fontSize: '11px' }}
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleDropdown(index);
                            }}
                          >
                            <span>{selectedValues.length === 0 ? 'All' : `${selectedValues.length} selected`}</span>
                            <span style={{ fontSize: '8px' }}>{dropdownOpen[index] ? '▲' : '▼'}</span>
                          </button>
                          {dropdownOpen[index] && (
                            <div 
                              className="position-absolute bg-white border rounded shadow-sm" 
                              style={{ 
                                top: '100%', 
                                left: 0, 
                                right: 0, 
                                maxHeight: '200px', 
                                overflowY: 'auto', 
                                zIndex: 1000,
                                fontSize: '12px'
                              }}
                            >
                              <div className="p-2 border-bottom">
                                <button
                                  className="btn btn-sm btn-link p-0 text-decoration-none"
                                  style={{ fontSize: '11px' }}
                                  onClick={(e) => {
                                    e.preventDefault();
                                    setFilters(prev => ({ ...prev, [index]: [] }));
                                  }}
                                >
                                  Clear All
                                </button>
                              </div>
                              {uniqueValues.map(value => (
                                <div key={value} className="p-2 d-flex align-items-center" style={{ cursor: 'pointer' }}>
                                  <input
                                    type="checkbox"
                                    className="form-check-input me-2"
                                    checked={selectedValues.includes(value)}
                                    onChange={(e) => handleCheckboxFilterChange(index, value, e.target.checked)}
                                    onClick={(e) => e.stopPropagation()}
                                  />
                                  <label 
                                    className="mb-0 flex-grow-1" 
                                    style={{ cursor: 'pointer', fontSize: '11px' }}
                                    onClick={() => handleCheckboxFilterChange(index, value, !selectedValues.includes(value))}
                                  >
                                    {value}
                                  </label>
                                </div>
                              ))}
                              {uniqueValues.length === 0 && (
                                <div className="p-2 text-muted" style={{ fontSize: '11px' }}>
                                  No values available
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {processedRows.map((row, rowIndex) => (
                <tr key={rowIndex} className={rowIndex % 2 === 0 ? 'even' : 'odd'}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className={cellIndex < (tableProperties?.group_by?.length || 0) ? 'group-by-cell' : 'metric-cell'}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default MetricsTable;