import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { Duration } from 'luxon';
import Plotly from 'plotly.js-dist-min';
import { Button, ButtonGroup, Dropdown, Form } from 'react-bootstrap';
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
  const [selectedMetrics, setSelectedMetrics] = useState([]);
  
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
  
  // Function to format cell values based on field name and content
  const formatCellValue = (header, value) => {
    if (value === null || value === undefined) return 'N/A';
    
    // Don't format forecast_lead_time_bin - show raw values
    if (header.toLowerCase().includes('forecast_lead_time_bin')) {
      return value;
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
  
  // Initialize selectedMetrics with all metrics when tableProperties changes
  useEffect(() => {
    if (tableProperties?.metrics?.length > 0) {
      setSelectedMetrics(tableProperties.metrics.slice());
    }
  }, [tableProperties]);
  
  // Handle metrics filter change
  const handleMetricFilterChange = (metric, checked) => {
    setSelectedMetrics(prev => {
      if (checked) {
        return [...prev, metric];
      } else {
        return prev.filter(m => m !== metric);
      }
    });
  };
  
  // Clear all metrics filters
  const clearMetricsFilter = () => {
    if (tableProperties?.metrics?.length > 0) {
      setSelectedMetrics(tableProperties.metrics.slice());
    }
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
    const filteredMetricFields = metricFields.filter(field => selectedMetrics.includes(field));
    const headers = [...groupByFields, ...filteredMetricFields];
    
    // Build rows directly from the sorted data
    const rows = sortedMetrics.map(item => {
      return headers.map(header => {
        const value = item[header];
        return formatCellValue(header, value);
      });
    });
    
    return { headers, rows, hasLeadTimeBin };
  }, [metrics, tableProperties, selectedMetrics]);
  
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
    
    // Map filtered data back to original raw metrics for duration parsing
    const rawDataForPlot = filteredData.map(filteredItem => {
      // Find the corresponding raw metric item
      const rawItem = metrics.find(metric => {
        // Match on all group_by fields to find the right raw item
        return groupByFields.every(field => {
          const filteredValue = filteredItem[field];
          const rawValue = metric[field];
          // Compare formatted vs raw values - need to check if they match conceptually
          return filteredValue === formatCellValue(field, rawValue) || filteredValue === rawValue;
        });
      });
      return rawItem || filteredItem; // Fallback to filtered item if no raw match found
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
      
      metricFields.filter(metric => selectedMetrics.includes(metric)).forEach(metric => {
        // Create step plot data using bin start values only
        const stepXValues = [];
        const stepYValues = [];
        
        // Now we can use the sorted group data directly since forecast_lead_time_bin is not formatted
        sortedGroupData.forEach((item, index) => {
          const binValue = item[leadTimeBinField]; // Raw duration like "PT6H_PT12H"
          const yValue = typeof item[metric] === 'string' ? parseFloat(item[metric]) : item[metric];
          
          let startHours = 0;
          
          if (binValue && binValue.includes('_')) {
            // Parse BINSTART_BINEND format - only use the start value
            const [startStr] = binValue.split('_');
            
            try {
              const startDuration = Duration.fromISO(startStr);
              if (startDuration.isValid) {
                startHours = startDuration.as('hours');
              } else {
                // Fallback to the original parsing function
                startHours = parseDurationForSort(startStr) / (1000 * 60 * 60);
              }
            } catch (e) {
              console.warn('Error parsing bin start duration:', startStr, e);
              return;
            }
          } else {
            // Single duration - use as start time
            try {
              const duration = Duration.fromISO(binValue);
              if (duration.isValid) {
                startHours = duration.as('hours');
              } else {
                startHours = parseDurationForSort(binValue) / (1000 * 60 * 60);
              }
            } catch (e) {
              console.warn('Error parsing single duration:', binValue, e);
              return;
            }
          }
          
          // Add the data point (only start time needed for step plot)
          stepXValues.push(startHours);
          stepYValues.push(yValue);
        });
        
        console.log(`Final ${metric} data:`, { 
          xRange: [Math.min(...stepXValues), Math.max(...stepXValues)], 
          yRange: [Math.min(...stepYValues), Math.max(...stepYValues)],
          totalPoints: stepXValues.length
        });
        
        // Create trace name combining group and metric (only for relevant columns)
        const traceName = relevantGroupByFields.length > 0 
          ? `${metric} (${groupKey})`
          : metric;
        
        traces.push({
          x: stepXValues,
          y: stepYValues,
          type: 'scatter',
          mode: 'lines',
          line: { 
            width: 2,
            shape: 'hv' // Horizontal then vertical for step effect
          },
          name: traceName,
          // Add hover info showing the relevant group values only
          hovertemplate: relevantGroupByFields.length > 0 
            ? `${metric}<br>${groupKey}<br>Lead Time: %{x:.1f}h<br>Value: %{y}<extra></extra>`
            : `${metric}<br>Lead Time: %{x:.1f}h<br>Value: %{y}<extra></extra>`
        });
        
        // Print the actual trace values
        console.log(`TRACE VALUES for ${traceName}:`);
        console.log('X Values:', stepXValues);
        console.log('Y Values:', stepYValues);
      });
    });
    
    return traces;
  }, [processedRows, headers, tableProperties, hasLeadTimeBin, selectedMetrics]);
  
  // Effect to render plot when in plot mode
  useEffect(() => {
    if (currentViewMode === 'plot' && hasLeadTimeBin && plotRef.current && plotData.length > 0) {
      const layout = {
        title: 'Metrics by Lead Time Bin',
        xaxis: { 
          title: 'Lead Time (hours)',
          type: 'linear',
          showgrid: true,
          gridcolor: 'rgba(0,0,0,0.1)'
        },
        yaxis: { 
          title: 'Metric Value',
          showgrid: true,
          gridcolor: 'rgba(0,0,0,0.1)'
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
      
      {currentViewMode === 'filters' && tableProperties?.group_by?.length > 0 ? (
        <div key="filters-view" className="table-filters p-4">
          <div className="row">
            <div className="col-12 mb-3">
              <h5 className="text-muted">Filter Options</h5>
              <p className="text-muted small">Select values to filter the data. Switch to Table or Plot view to see results.</p>
            </div>
            {headers.slice(0, tableProperties.group_by.length).map((header, index) => {
              const uniqueValues = uniqueValuesByColumn[index] || [];
              const selectedValues = filters[index] || [];
              
              return (
                <div key={index} className="col-lg-4 col-md-6 mb-3">
                  <label className="form-label fw-bold">{header}</label>
                  <Dropdown className="w-100">
                    <Dropdown.Toggle 
                      variant="outline-secondary" 
                      className="w-100 d-flex justify-content-between align-items-center"
                      style={{ fontSize: '14px' }}
                    >
                      <span>{selectedValues.length === 0 ? 'All' : `${selectedValues.length} selected`}</span>
                    </Dropdown.Toggle>

                    <Dropdown.Menu 
                      style={{ 
                        minWidth: '250px',
                        maxHeight: '300px', 
                        overflowY: 'auto'
                      }}
                    >
                      <Dropdown.Header>
                        <button
                          className="btn btn-sm btn-link p-0 text-decoration-none"
                          onClick={(e) => {
                            e.preventDefault();
                            setFilters(prev => ({ ...prev, [index]: [] }));
                          }}
                        >
                          Clear All
                        </button>
                      </Dropdown.Header>
                      
                      <Dropdown.Divider />
                      
                      {uniqueValues.map(value => (
                        <Dropdown.Item 
                          key={value} 
                          as="div" 
                          className="p-0"
                          onClick={(e) => e.preventDefault()}
                        >
                          <div className="px-3 py-2">
                            <Form.Check
                              type="checkbox"
                              id={`filter-${index}-${value}`}
                              label={value}
                              checked={selectedValues.includes(value)}
                              onChange={(e) => handleCheckboxFilterChange(index, value, e.target.checked)}
                              className="mb-0"
                            />
                          </div>
                        </Dropdown.Item>
                      ))}
                      
                      {uniqueValues.length === 0 && (
                        <Dropdown.Item disabled>
                          No values available
                        </Dropdown.Item>
                      )}
                    </Dropdown.Menu>
                  </Dropdown>
                </div>
              );
            })}
            
            {/* Metrics filter section */}
            {tableProperties?.metrics?.length > 0 && (
              <>
                <div className="col-12 mt-4 mb-3">
                  <hr />
                  <h6 className="text-muted">Select Metrics</h6>
                  <p className="text-muted small">Choose which metrics to display in the table and plot.</p>
                </div>
                <div className="col-12">
                  <Dropdown className="w-100">
                    <Dropdown.Toggle 
                      variant="outline-secondary" 
                      className="w-100 d-flex justify-content-between align-items-center"
                      style={{ fontSize: '14px' }}
                    >
                      <span>{selectedMetrics.length === 0 ? 'No metrics' : selectedMetrics.length === tableProperties.metrics.length ? 'All metrics' : `${selectedMetrics.length} of ${tableProperties.metrics.length} metrics`}</span>
                    </Dropdown.Toggle>

                    <Dropdown.Menu 
                      style={{ 
                        minWidth: '300px',
                        maxHeight: '300px', 
                        overflowY: 'auto'
                      }}
                    >
                      <Dropdown.Header>
                        <div className="d-flex justify-content-between">
                          <button
                            className="btn btn-sm btn-link p-0 text-decoration-none"
                            onClick={(e) => {
                              e.preventDefault();
                              clearMetricsFilter();
                            }}
                          >
                            Select All
                          </button>
                          <button
                            className="btn btn-sm btn-link p-0 text-decoration-none text-danger"
                            onClick={(e) => {
                              e.preventDefault();
                              setSelectedMetrics([]);
                            }}
                          >
                            Clear All
                          </button>
                        </div>
                      </Dropdown.Header>
                      
                      <Dropdown.Divider />
                      
                      {tableProperties.metrics.map(metric => (
                        <Dropdown.Item 
                          key={metric} 
                          as="div" 
                          className="p-0"
                          onClick={(e) => e.preventDefault()}
                        >
                          <div className="px-3 py-2">
                            <Form.Check
                              type="checkbox"
                              id={`metric-${metric}`}
                              label={metric}
                              checked={selectedMetrics.includes(metric)}
                              onChange={(e) => handleMetricFilterChange(metric, e.target.checked)}
                              className="mb-0"
                            />
                          </div>
                        </Dropdown.Item>
                      ))}
                    </Dropdown.Menu>
                  </Dropdown>
                </div>
              </>
            )}
            
            {/* Active filters summary and clear all */}
            {Object.keys(filters).length > 0 && Object.values(filters).some(f => Array.isArray(f) ? f.length > 0 : f) && (
              <div className="col-12 mt-3">
                <div className="alert alert-info d-flex justify-content-between align-items-center">
                  <span>
                    <strong>Active Filters:</strong> {Object.values(filters).reduce((total, f) => total + (Array.isArray(f) ? f.length : 0), 0)} selections
                  </span>
                  <button 
                    className="btn btn-sm btn-outline-danger"
                    onClick={clearFilters}
                  >
                    Clear All Filters
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      ) : currentViewMode === 'plot' && hasLeadTimeBin ? (
        <div key="plot-view" className="metrics-plot-container" style={{ height: '400px', padding: '10px' }}>
          <div ref={plotRef} style={{ width: '100%', height: '100%' }} />
        </div>
      ) : (
        <div key="table-view" className="metrics-table-wrapper" style={{ overflowX: 'auto' }}>
          {/* Existing filter controls display */}
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
                  
                  return (
                    <th key={index} 
                        className={isGroupByColumn ? 'group-by-header' : 'metric-header'}
                        style={{ minWidth: '120px' }}
                    >
                      <div 
                        className="sortable-header"
                        onClick={() => handleSort(index, header)}
                        style={{ 
                          cursor: 'pointer', 
                          display: 'flex', 
                          alignItems: 'center', 
                          justifyContent: 'space-between',
                          userSelect: 'none',
                          padding: '8px 4px'
                        }}
                      >
                        <span>{header}</span>
                        <span className="sort-indicator">
                          {sortConfig.column === index && (
                            sortConfig.direction === 'asc' ? '▲' : '▼'
                          )}
                        </span>
                      </div>
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