import React from 'react';
import './MetricsTable.css';

const MetricsTable = ({ 
  metrics = [], 
  loading = false, 
  error = null,
  title = "Metrics",
  emptyMessage = "No metrics available for this location.",
  showTitle = true
}) => {
  
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

  if (!metrics || metrics.length === 0) {
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
          <span className="metrics-count">({metrics.length} metrics)</span>
        </div>
      )}
      <div className="metrics-table-wrapper">
        <table className="metrics-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((metric, index) => (
              <tr key={index} className={index % 2 === 0 ? 'even' : 'odd'}>
                <td className="metric-name">{metric.metric_name || metric.name || 'Unknown'}</td>
                <td className="metric-value">
                  {metric.metric_value !== null && metric.metric_value !== undefined 
                    ? typeof metric.metric_value === 'number' 
                      ? metric.metric_value.toFixed(4)
                      : metric.metric_value
                    : 'N/A'
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default MetricsTable;