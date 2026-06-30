import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';
import { useGriddedDashboard } from '../../../context/GriddedDashboardContext.jsx';
import DashboardPanel from '../../common/dashboard/DashboardPanel.jsx';

const GriddedTimeseriesPanel = () => {
  const { state } = useGriddedDashboard();
  const { timeseriesData, timeseriesLoading, timeseriesError, clickedPoint } = state;
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current || !timeseriesData) return;
    const { times, values, lon, lat, variable } = timeseriesData;
    Plotly.react(
      plotRef.current,
      [
        {
          x: times,
          y: values,
          type: 'scatter',
          mode: 'lines+markers',
          marker: { size: 4 },
          line: { color: '#0d6efd' },
          name: variable,
        },
      ],
      {
        title: {
          text: `${variable} at (${lat.toFixed(4)}°N, ${lon.toFixed(4)}°E)`,
          font: { size: 13 },
        },
        xaxis: { title: 'Time', type: 'date' },
        yaxis: { title: variable },
        margin: { t: 40, r: 20, b: 50, l: 60 },
        autosize: true,
      },
      { responsive: true, displayModeBar: false },
    );
  }, [timeseriesData]);

  const header = <span className="small fw-bold">Timeseries</span>;

  if (!clickedPoint && !timeseriesData && !timeseriesLoading && !timeseriesError) {
    return (
      <DashboardPanel header={header} style={{ height: '100%' }}>
        <div className="d-flex align-items-center justify-content-center h-100 text-muted small">
          Click a point on the map to view a timeseries
        </div>
      </DashboardPanel>
    );
  }

  return (
    <DashboardPanel
      header={header}
      style={{ height: '100%' }}
      bodyStyle={{ padding: 0, overflow: 'hidden', height: '100%' }}
    >
      {timeseriesLoading && (
        <div className="d-flex align-items-center justify-content-center h-100">
          <div className="spinner-border spinner-border-sm text-primary me-2" />
          <span className="small text-muted">Loading timeseries…</span>
        </div>
      )}
      {timeseriesError && !timeseriesLoading && (
        <div className="d-flex align-items-center justify-content-center h-100">
          <span className="small text-danger">Error: {timeseriesError}</span>
        </div>
      )}
      {timeseriesData && !timeseriesLoading && (
        <div ref={plotRef} style={{ width: '100%', height: '100%' }} />
      )}
    </DashboardPanel>
  );
};

export default GriddedTimeseriesPanel;
