import React from 'react';
import { useDashboard } from '../context/DashboardContext.jsx';
import { useFilters, useDataFetching, useLocationSelection } from '../hooks/useDataFetching';

const TimeseriesControls = () => {
  const { state } = useDashboard();
  const { timeseriesFilters, updateTimeseriesFilters } = useFilters();
  const { loadTimeseries } = useDataFetching();
  const { selectedLocation } = useLocationSelection();
  
  const handleTimeseriesFilterChange = (filterType, value) => {
    updateTimeseriesFilters({ [filterType]: value });
  };
  
  const handleLoadTimeseries = async () => {
    if (!selectedLocation) {
      alert('Please select a location first');
      return;
    }
    
    await loadTimeseries({
      location_id: selectedLocation.location_id,
      configuration: timeseriesFilters.configuration,
      variable: timeseriesFilters.variable,
      start_date: timeseriesFilters.start_date,
      end_date: timeseriesFilters.end_date,
      reference_time: timeseriesFilters.reference_time
    });
  };

  return (
    <div style={{ padding: '20px' }}>
      <div className="mb-3">
          <label className="form-label">Configuration</label>
          <select 
            className="form-select form-select-sm" 
            value={timeseriesFilters.configuration || ''}
            onChange={(e) => handleTimeseriesFilterChange('configuration', e.target.value)}
          >
            <option value="">Select Configuration</option>
            {state.configurations.map(config => (
              <option key={config} value={config}>{config}</option>
            ))}
          </select>
        </div>
        
        <div className="mb-3">
          <label className="form-label">Variable</label>
          <select 
            className="form-select form-select-sm" 
            value={timeseriesFilters.variable || ''}
            onChange={(e) => handleTimeseriesFilterChange('variable', e.target.value)}
          >
            <option value="">Select Variable</option>
            {state.variables.map(variable => (
              <option key={variable} value={variable}>{variable}</option>
            ))}
          </select>
        </div>
        
        <div className="mb-3 mt-3">
          <label className="form-label">Value Time Range (optional)</label>
          <div className="row">
            <div className="col-6">
              <label className="form-label small">Start Date</label>
              <input 
                type="datetime-local" 
                className="form-control form-control-sm" 
                value={timeseriesFilters.start_date || ''}
                onChange={(e) => handleTimeseriesFilterChange('start_date', e.target.value)}
              />
            </div>
            <div className="col-6">
              <label className="form-label small">End Date</label>
              <input 
                type="datetime-local" 
                className="form-control form-control-sm" 
                value={timeseriesFilters.end_date || ''}
                onChange={(e) => handleTimeseriesFilterChange('end_date', e.target.value)}
              />
            </div>
          </div>
        </div>
        
        <div className="mb-3 mt-3">
          <label className="form-label">Reference Time Range (optional)</label>
          <div className="row">
            <div className="col-6">
              <label className="form-label small">Start Reference Time</label>
              <input 
                type="datetime-local" 
                className="form-control form-control-sm" 
                value={timeseriesFilters.reference_time_start || ''}
                onChange={(e) => handleTimeseriesFilterChange('reference_time_start', e.target.value)}
              />
            </div>
            <div className="col-6">
              <label className="form-label small">End Reference Time</label>
              <input 
                type="datetime-local" 
                className="form-control form-control-sm" 
                value={timeseriesFilters.reference_time_end || ''}
                onChange={(e) => handleTimeseriesFilterChange('reference_time_end', e.target.value)}
              />
            </div>
          </div>
        </div>
        
        <div className="d-grid">
          <button 
            className="btn btn-primary"
            onClick={handleLoadTimeseries}
            disabled={!selectedLocation || !timeseriesFilters.configuration || !timeseriesFilters.variable || state.timeseriesLoading}
          >
            {state.timeseriesLoading ? (
              <>
                <span className="spinner-border spinner-border-sm me-2" role="status">
                  <span className="visually-hidden">Loading...</span>
                </span>
                Loading...
              </>
            ) : (
              'Load Timeseries'
            )}
          </button>
        </div>
    </div>
  );
};

export default TimeseriesControls;