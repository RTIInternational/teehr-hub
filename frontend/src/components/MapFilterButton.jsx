import React, { useState } from 'react';
import { Dropdown, Button, Form, Card } from 'react-bootstrap';
import { useDashboard } from '../context/DashboardContext.jsx';
import { useFilters, useDataFetching } from '../hooks/useDataFetching';

const MapFilterButton = () => {
  const [showDropdown, setShowDropdown] = useState(false);
  const { state } = useDashboard();
  const { mapFilters, updateMapFilters } = useFilters();
  const { loadLocations } = useDataFetching();

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

  const getMetricLabel = (metric) => {
    const labels = {
      nash_sutcliffe_efficiency: 'Nash-Sutcliffe Efficiency',
      kling_gupta_efficiency: 'Kling-Gupta Efficiency'
    };
    
    // Return predefined label if exists, otherwise convert snake_case to Title Case
    return labels[metric] || metric.split('_').map(word => 
      word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    ).join(' ');
  };

  return (
    <div className="position-absolute" style={{ top: '10px', right: '10px', zIndex: 1000 }}>
      <Dropdown show={showDropdown} onToggle={setShowDropdown} align="end">
        <Dropdown.Toggle 
          variant="light" 
          size="sm" 
          className="shadow"
          style={{ minWidth: '120px' }}
        >
          🗺️ Map Filters
        </Dropdown.Toggle>
        
        <Dropdown.Menu style={{ minWidth: '280px' }}>
          <div className="p-3">
            <h6 className="mb-3">Filter Map Locations</h6>
            
            <Form.Group className="mb-3">
              <Form.Label className="small">Configuration</Form.Label>
              <Form.Select 
                size="sm" 
                value={mapFilters.configuration || ''}
                onChange={(e) => handleMapFilterChange('configuration', e.target.value)}
              >
                <option value="">Select Configuration</option>
                {state.configurations.map(config => (
                  <option key={config} value={config}>{config}</option>
                ))}
              </Form.Select>
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label className="small">Variable</Form.Label>
              <Form.Select 
                size="sm" 
                value={mapFilters.variable || ''}
                onChange={(e) => handleMapFilterChange('variable', e.target.value)}
              >
                <option value="">Select Variable</option>
                {state.variables.map(variable => (
                  <option key={variable} value={variable}>{variable}</option>
                ))}
              </Form.Select>
            </Form.Group>
            
            <Form.Group className="mb-2">
              <Form.Label className="small">Metric</Form.Label>
              <Form.Select 
                size="sm" 
                value={mapFilters.metric || ''}
                onChange={(e) => handleMapFilterChange('metric', e.target.value)}
              >
                <option value="">Select Metric</option>
                {state.metrics.map(metric => (
                  <option key={metric} value={metric}>
                    {getMetricLabel(metric)}
                  </option>
                ))}
              </Form.Select>
            </Form.Group>
          </div>
        </Dropdown.Menu>
      </Dropdown>
    </div>
  );
};

export default MapFilterButton;