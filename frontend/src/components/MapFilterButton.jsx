import React, { useState } from 'react';
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
      bias: 'Bias',
      nash_sutcliffe_efficiency: 'Nash-Sutcliffe Efficiency',
      kling_gupta_efficiency: 'Kling-Gupta Efficiency',
      mean_error: 'Mean Error',
      mean_squared_error: 'Mean Squared Error',
      root_mean_squared_error: 'Root Mean Squared Error'
    };
    return labels[metric] || metric;
  };

  return (
    <div className="position-absolute" style={{ top: '10px', right: '10px', zIndex: 1000 }}>
      <div className="dropdown">
        <button
          className="btn btn-light btn-sm shadow"
          type="button"
          onClick={() => setShowDropdown(!showDropdown)}
          style={{ minWidth: '120px' }}
        >
          🗺️ Map Filters
          <i className={`ms-2 bi bi-chevron-${showDropdown ? 'up' : 'down'}`}></i>
        </button>
        
        {showDropdown && (
          <div 
            className="dropdown-menu show" 
            style={{ 
              minWidth: '280px',
              right: '0',
              left: 'auto',
              top: '100%'
            }}
          >
            <div className="p-3">
              <h6 className="dropdown-header">Filter Map Locations</h6>
              
              <div className="mb-3">
                <label className="form-label small">Configuration</label>
                <select 
                  className="form-select form-select-sm" 
                  value={mapFilters.configuration || ''}
                  onChange={(e) => handleMapFilterChange('configuration', e.target.value)}
                >
                  <option value="">Select Configuration</option>
                  {state.configurations.map(config => (
                    <option key={config} value={config}>{config}</option>
                  ))}
                </select>
              </div>
              
              <div className="mb-3">
                <label className="form-label small">Variable</label>
                <select 
                  className="form-select form-select-sm" 
                  value={mapFilters.variable || ''}
                  onChange={(e) => handleMapFilterChange('variable', e.target.value)}
                >
                  <option value="">Select Variable</option>
                  {state.variables.map(variable => (
                    <option key={variable} value={variable}>{variable}</option>
                  ))}
                </select>
              </div>
              
              <div className="mb-2">
                <label className="form-label small">Metric</label>
                <select 
                  className="form-select form-select-sm" 
                  value={mapFilters.metric || ''}
                  onChange={(e) => handleMapFilterChange('metric', e.target.value)}
                >
                  <option value="">Select Metric</option>
                  {state.metrics.map(metric => (
                    <option key={metric} value={metric}>
                      {getMetricLabel(metric)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MapFilterButton;