import { useEffect, useState } from 'react';
import { Card, Form, ButtonGroup, Button } from 'react-bootstrap';
import MetricsTable from './MetricsTable';

const LocationMetrics = ({ 
  selectedLocation, 
  locationMetrics, 
  metricsLoading, 
  error, 
  loadLocationMetrics,
  tableProperties = {}, // Available tables with their properties
  defaultTable = null // Default table to use
}) => {
  // Get available tables that have metrics
  const availableTables = Object.keys(tableProperties).filter(tableName => 
    tableProperties[tableName]?.metrics?.length > 0
  );
  
  // State for selected table and view mode
  const [selectedTable, setSelectedTable] = useState(
    defaultTable || availableTables[0] || null
  );
  const [viewMode, setViewMode] = useState('table');
  
  // Check if current table has group_by fields for filter capability
  const hasFilters = selectedTable && tableProperties[selectedTable]?.group_by?.length > 0;
  
  // Check if current table has lead time bins for plot capability
  const hasLeadTimeBin = selectedTable && tableProperties[selectedTable]?.group_by?.some(field => 
    field.toLowerCase().includes('lead_time_bin') || 
    field.toLowerCase().includes('forecast_lead_time_bin')
  );
  
  // Update selected table when default changes or tables become available
  useEffect(() => {
    if (!selectedTable && availableTables.length > 0) {
      setSelectedTable(defaultTable || availableTables[0]);
    }
  }, [defaultTable, availableTables, selectedTable]);

  // Load metrics when location or table selection changes
  useEffect(() => {
    if (selectedLocation?.primary_location_id && selectedTable) {
      loadLocationMetrics(selectedLocation.primary_location_id, selectedTable);
    }
  }, [selectedLocation?.primary_location_id, selectedTable, loadLocationMetrics]);

  if (!selectedLocation) {
    return null;
  }

  return (
    <Card className="shadow-lg h-100" style={{ borderRadius: '8px', display: 'flex', flexDirection: 'column' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center">
        <div className="d-flex align-items-center gap-2">
          <Card.Title as="h6" className="mb-0">📊 Metrics</Card.Title>
          {(hasLeadTimeBin || hasFilters) && (
            <ButtonGroup size="sm">
              {hasFilters && (
                <Button 
                  variant={viewMode === 'filters' ? 'primary' : 'outline-primary'}
                  onClick={() => setViewMode('filters')}
                  style={{ fontSize: '11px' }}
                >
                  🔍 Filters
                </Button>
              )}
              <Button 
                variant={viewMode === 'table' ? 'primary' : 'outline-primary'}
                onClick={() => setViewMode('table')}
                style={{ fontSize: '11px' }}
              >
                📊 Table
              </Button>
              {hasLeadTimeBin && (
                <Button 
                  variant={viewMode === 'plot' ? 'primary' : 'outline-primary'}
                  onClick={() => setViewMode('plot')}
                  style={{ fontSize: '11px' }}
                >
                  📈 Plot
                </Button>
              )}
            </ButtonGroup>
          )}
        </div>
        <div className="d-flex align-items-center gap-2">
          {availableTables.length > 1 && (
            <Form.Select
              size="sm"
              value={selectedTable || ''}
              onChange={(e) => setSelectedTable(e.target.value)}
              style={{ width: 'auto', minWidth: '200px' }}
            >
            <option value="">Select Table...</option>
            {availableTables.map(tableName => {
              const description = tableProperties[tableName]?.description || tableName;
              return (
                <option key={tableName} value={tableName}>
                  {description}
                </option>
              );
            })}
            </Form.Select>
          )}
        </div>
      </Card.Header>
      <Card.Body className="p-0 flex-grow-1" style={{ overflow: 'auto' }}>
        <MetricsTable
          metrics={locationMetrics}
          loading={metricsLoading}
          error={error}
          title="Metrics"
          emptyMessage={selectedTable ? `No metrics available for this location in ${selectedTable}.` : "Select a table to view metrics."}
          showTitle={false}
          tableProperties={selectedTable ? tableProperties[selectedTable] : null}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
        />
      </Card.Body>
    </Card>
  );
};

export default LocationMetrics;