import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import DashboardPanel from '@/shared/components/DashboardPanel';
import { useEdrTimeseries } from '@/shared/queries/gridded/edr';
import { useTimesteps } from '@/shared/queries/gridded/timesteps';
import { useVariableAttrs } from '@/shared/queries/gridded/variableAttrs';

import { useDashboard } from '../DashboardContext';

const GriddedTimeseriesPanel = () => {
  const { state } = useDashboard();
  const { mapFilters, clickedPoint } = state;
  const plotRef = useRef(null);

  const timesteps = useTimesteps(mapFilters.dataset);
  const variableAttrs = useVariableAttrs(mapFilters.dataset);
  const timeseries = useEdrTimeseries({
    datasetId: mapFilters.dataset,
    variable: mapFilters.variable,
    lat: clickedPoint?.lat,
    lon: clickedPoint?.lon,
    timesteps: timesteps.data,
  });

  useEffect(() => {
    if (!plotRef.current || !timeseries.data) return;
    const { times, values, lon, lat, variable, source, location_id, name } = timeseries.data;
    const units = variableAttrs.data?.[variable]?.units
      ? ` (${variableAttrs.data?.[variable].units})`
      : '';

    // The plot shows one series at a time — whichever query ran last. The title
    // says where it came from so a gridded point and a polygon aren't confused.
    let plotTitle;
    if (source === 'warehouse') {
      plotTitle = `${variable}${units} at ${name ? `${name} (${location_id})` : location_id}`;
    } else {
      const latHem = lat >= 0 ? 'N' : 'S';
      const lonHem = lon >= 0 ? 'E' : 'W';
      plotTitle = `${variable}${units} at (${Math.abs(lat).toFixed(4)}°${latHem}, ${Math.abs(lon).toFixed(4)}°${lonHem})`;
    }

    void Plotly.react(
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
        title: { text: plotTitle, font: { size: 13 } },
        xaxis: { title: 'Time', type: 'date' },
        yaxis: { title: variable },
        margin: { t: 40, r: 20, b: 50, l: 60 },
        autosize: true,
      } as Partial<Plotly.Layout>,
      { responsive: true, displayModeBar: false }
    );
  }, [timeseries.data, variableAttrs]);

  const header = (
    <span className="small fw-bold">
      Timeseries
      {timeseries.data?.source && (
        <span className="text-muted fw-normal ms-2">
          {timeseries.data.source === 'warehouse' ? 'Warehouse (polygon)' : 'Gridded (point)'}
        </span>
      )}
    </span>
  );

  if (!clickedPoint && !timeseries.data && !timeseries.isLoading && !timeseries.isError) {
    return (
      <DashboardPanel header={header} style={{ height: '100%' }}>
        <div className="d-flex align-items-center justify-content-center h-100 text-muted small">
          Click a point on the map, or load a timeseries for a selected polygon
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
      {timeseries.isLoading && (
        <div className="d-flex align-items-center justify-content-center h-100">
          <div className="spinner-border spinner-border-sm text-primary me-2" />
          <span className="small text-muted">Loading timeseries…</span>
        </div>
      )}
      {timeseries.isError && !timeseries.isLoading && (
        <div className="d-flex align-items-center justify-content-center h-100">
          <span className="small text-danger">Error: {timeseries.error.message}</span>
        </div>
      )}
      {timeseries.data && !timeseries.isLoading && (
        <div ref={plotRef} style={{ width: '100%', height: '100%' }} />
      )}
    </DashboardPanel>
  );
};

export default GriddedTimeseriesPanel;
