import { useState } from 'react';
import { Dropdown, Form } from 'react-bootstrap';

const MapFilterButton = ({ 
  state, 
  mapFilters, 
  updateMapFilters, 
  loadLocations 
}) => {
  const [showDropdown, setShowDropdown] = useState(false);

  const handleMapFilterChange = async (filterType, value) => {
    const newFilters = { ...mapFilters, [filterType]: value };
    updateMapFilters({ [filterType]: value });
    
    // Reload locations when configuration or variable changes
    if (filterType === 'configuration' || filterType === 'variable') {
      await loadLocations({
        configuration: newFilters.configuration,
        variable: newFilters.variable
      });
    }
  };

  return (
    <div className="position-absolute top-0 end-0 m-3" style={{ zIndex: 1000 }}>
      <Dropdown show={showDropdown} onToggle={setShowDropdown}>
        <Dropdown.Toggle variant="light" className="shadow-sm">
          🗺️ Map Filters
        </Dropdown.Toggle>

        <Dropdown.Menu style={{ minWidth: '300px' }}>
          <div className="p-3">
            <h6 className="dropdown-header px-0">Map Display Settings</h6>
            
            {/* Configuration Filter */}
            <Form.Group className="mb-3">
              <Form.Label className="small fw-bold">Configuration</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.configuration || ''}
                onChange={(e) => handleMapFilterChange('configuration', e.target.value || null)}
              >
                <option value="">Select Configuration...</option>
                {Array.isArray(state.configurations) && state.configurations.map((config) => (
                  <option key={config} value={config}>
                    {config}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>

            {/* Variable Filter */}
            <Form.Group className="mb-3">
              <Form.Label className="small fw-bold">Variable</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.variable || ''}
                onChange={(e) => handleMapFilterChange('variable', e.target.value || null)}
              >
                <option value="">Select Variable...</option>
                {Array.isArray(state.variables) && state.variables.map((variable) => (
                  <option key={variable} value={variable}>
                    {variable}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>

            {/* Metric Filter */}
            <Form.Group className="mb-0">
              <Form.Label className="small fw-bold">Color By Metric</Form.Label>
              <Form.Select
                size="sm"
                value={mapFilters.metricName || ''}
                onChange={(e) => handleMapFilterChange('metricName', e.target.value || null)}
              >
                <option value="">Select Metric...</option>
                {(() => {
                  // Try to find metrics from any available table in the batch response
                  // This works for both single-table and multi-table dashboards
                  const allTableProps = state.tableProperties || {};
                  const allMetrics = [];
                  
                  // Collect all unique metrics from all tables
                  Object.values(allTableProps).forEach(tableProps => {
                    if (Array.isArray(tableProps?.metrics)) {
                      tableProps.metrics.forEach(metric => {
                        if (!allMetrics.includes(metric)) {
                          allMetrics.push(metric);
                        }
                      });
                    }
                  });
                  
                  return allMetrics.map((metricName) => (
                    <option key={metricName} value={metricName}>
                      {metricName}
                    </option>
                  ));
                })()}
              </Form.Select>
            </Form.Group>
          </div>
        </Dropdown.Menu>
      </Dropdown>
    </div>
  );
};

export default MapFilterButton;