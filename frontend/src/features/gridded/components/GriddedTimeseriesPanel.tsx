import { useQueries } from '@tanstack/react-query';
import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef, useState } from 'react';
import { Button, ButtonGroup, Spinner } from 'react-bootstrap';

import DashboardPanel from '@/shared/components/DashboardPanel';
import { useEdrTimeseries } from '@/shared/queries/gridded/edr';
import { usePolygonTimeseries } from '@/shared/queries/gridded/polygonTimeseries';
import { variableAttrsQueryOptions } from '@/shared/queries/gridded/variableAttrs';
import { parseUtcTime, shortestStep } from '@/shared/utils/dates';
import { formatUnitName, formatVariableName } from '@/shared/utils/formatters';
import { seriesColor } from '@/shared/utils/plotColors';

import { ActionTypes, timeseriesDatasets, useDashboard } from '../DashboardContext';
import GriddedTimeseriesControls from './GriddedTimeseriesControls';

const formatPoint = (lat: number, lon: number) =>
  `(${Math.abs(lat).toFixed(4)}°${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(4)}°${lon >= 0 ? 'E' : 'W'})`;

type PlotSeries = {
  name: string;
  variable: string;
  unit: string;
  times: string[];
  values: (number | null)[];
};

type PlotData = { plotted: PlotSeries[]; notes: string[]; isLoading: boolean };

// Break the line across missing steps: a gap longer than the series' shortest step gets a null
const withGaps = ({ times, values }: PlotSeries) => {
  const ms = times.map(parseUtcTime);
  const step = shortestStep(ms);
  const x: string[] = [];
  const y: (number | null)[] = [];
  times.forEach((time, i) => {
    if (i > 0 && ms[i] - ms[i - 1] > step) {
      x.push(new Date(ms[i - 1] + step).toISOString().slice(0, 19));
      y.push(null);
    }
    x.push(time);
    y.push(values[i]);
  });
  return { x, y };
};

const GriddedTimeseriesPanel = () => {
  const { state, dispatch } = useDashboard();
  const { mapFilters, clickedPoint, polygonQuery, timeseriesFilters } = state;
  const plotRef = useRef<HTMLDivElement>(null);
  const [viewMode, setViewMode] = useState('plot');

  // A new map click or polygon load shows its plot
  const request = clickedPoint ?? polygonQuery;
  const [lastRequest, setLastRequest] = useState(request);
  if (request !== lastRequest) {
    setLastRequest(request);
    if (request) setViewMode('plot');
  }

  const datasets = timeseriesDatasets(timeseriesFilters, mapFilters.dataset);
  const series = useEdrTimeseries({
    ...timeseriesFilters,
    datasets,
    preferredVariable: mapFilters.variable,
    lon: clickedPoint?.lon,
    lat: clickedPoint?.lat,
    anchor: clickedPoint?.time,
  });
  const variableAttrs = useQueries({
    queries: datasets.map((ds) => variableAttrsQueryOptions(ds)),
  });
  const polygonSeries = usePolygonTimeseries({
    ...timeseriesFilters,
    datasets,
    locationId: polygonQuery?.location_id,
    variable: mapFilters.variable,
    anchor: polygonQuery?.time,
  });

  // Point and polygon queries plot through the same series shape
  const { plotted, notes, isLoading }: PlotData = polygonQuery
    ? {
        plotted: (polygonSeries.data ?? []).map((ts) => ({
          name: ts.configuration_name,
          variable: formatVariableName(ts.variable_name),
          unit: formatUnitName(ts.unit_name),
          times: ts.timeseries.map((p) => p.value_time),
          values: ts.timeseries.map((p) => p.value),
        })),
        notes: polygonSeries.error ? [polygonSeries.error.message] : [],
        isLoading: polygonSeries.isLoading,
      }
    : {
        plotted: series.flatMap((s, i) =>
          s.data?.values.some((v) => v !== null)
            ? [
                {
                  name: s.datasetId,
                  variable: formatVariableName(s.variable ?? undefined),
                  unit: formatUnitName(
                    s.variable ? (variableAttrs[i]?.data?.[s.variable]?.units ?? null) : null
                  ),
                  ...s.data,
                },
              ]
            : []
        ),
        notes: series.flatMap((s) =>
          s.skipped ? [s.skipped] : s.error ? [`${s.datasetId}: ${s.error}`] : []
        ),
        isLoading: series.some((s) => s.isLoading),
      };
  const title = polygonQuery
    ? polygonQuery.name || polygonQuery.location_id
    : clickedPoint && formatPoint(clickedPoint.lat, clickedPoint.lon);

  useEffect(() => {
    if (!plotRef.current || !request || plotted.length === 0) return;
    const traces = plotted.map((s, i) => ({
      ...withGaps(s),
      name: `${s.name} · ${s.variable}${s.unit ? ` (${s.unit})` : ''}`,
      type: 'scatter',
      mode: 'lines+markers',
      connectgaps: false,
      marker: { size: 4 },
      line: { color: seriesColor(i) },
      hovertemplate:
        '<b>%{fullData.name}</b><br>' +
        'Date: %{x}<br>' +
        `${s.variable}: %{y}${s.unit ? ' ' + s.unit : ''}<br>` +
        '<extra></extra>',
    }));
    const sharedUnit = plotted.every((s) => s.unit === plotted[0].unit) ? plotted[0].unit : '';

    void Plotly.react(
      plotRef.current,
      traces as Partial<Plotly.ScatterData>[],
      {
        title: { text: title, font: { size: 13 } },
        xaxis: { title: 'Time', type: 'date' },
        yaxis: { title: sharedUnit || 'Value' },
        showlegend: true,
        legend: { orientation: 'h', y: -0.2 },
        margin: { t: 40, r: 20, b: 50, l: 60 },
        autosize: true,
      } as Partial<Plotly.Layout>,
      { responsive: true, displayModeBar: false }
    );
  });

  const header = (
    <div className="d-flex justify-content-between align-items-center">
      <span className="small fw-bold">Timeseries</span>
      <ButtonGroup size="sm">
        <Button
          variant={viewMode === 'filters' ? 'primary' : 'outline-primary'}
          onClick={() => setViewMode('filters')}
          style={{ fontSize: '11px' }}
        >
          🔍 Filters
        </Button>
        <Button
          variant={viewMode === 'plot' ? 'primary' : 'outline-primary'}
          onClick={() => setViewMode('plot')}
          style={{ fontSize: '11px' }}
        >
          📈 Plot
        </Button>
      </ButtonGroup>
    </div>
  );

  const notesList = notes.length > 0 && (
    <ul className="small text-muted mb-0 px-3 pb-2" style={{ flex: '0 0 auto' }}>
      {notes.map((note) => (
        <li key={note}>{note}</li>
      ))}
    </ul>
  );

  let body;
  if (viewMode === 'filters') {
    body = (
      <div className="p-3 h-100 overflow-auto">
        <GriddedTimeseriesControls
          timeseriesFilters={timeseriesFilters}
          updateTimeseriesFilters={(patch) =>
            dispatch({ type: ActionTypes.UPDATE_TIMESERIES_FILTERS, payload: patch })
          }
          activeDataset={mapFilters.dataset}
        />
      </div>
    );
  } else if (!request) {
    body = (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted small">
        Click a point on the map, or load a timeseries for a selected polygon
      </div>
    );
  } else if (isLoading) {
    body = (
      <div className="d-flex justify-content-center align-items-center h-100">
        <div className="text-center">
          <Spinner animation="border" variant="primary" />
          <div className="mt-2 small text-muted">Loading timeseries data...</div>
        </div>
      </div>
    );
  } else if (plotted.length === 0) {
    body = (
      <div className="d-flex flex-column align-items-center justify-content-center h-100">
        <div className="text-center text-muted">
          <div style={{ fontSize: '2rem' }}>📊</div>
          <h6>No Data Available</h6>
          <p className="small">Try switching to Filters to adjust the datasets or time span.</p>
        </div>
        {notesList}
      </div>
    );
  } else {
    // Keyed so React never reuses this div for another state with Plotly's nodes still in it
    body = (
      <div key="plot" className="d-flex flex-column h-100">
        <div ref={plotRef} style={{ flex: '1 1 auto', minHeight: 0, width: '100%' }} />
        {notesList}
      </div>
    );
  }

  return (
    <DashboardPanel
      header={header}
      style={{ height: '100%' }}
      bodyStyle={{ padding: 0, overflow: 'hidden', height: '100%' }}
    >
      {body}
    </DashboardPanel>
  );
};

export default GriddedTimeseriesPanel;
