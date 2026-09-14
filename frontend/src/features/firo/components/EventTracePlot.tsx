import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import type { EventTraceDataResponse } from '../hooks/useEventTraceInitializations';

type EventTracePlotProps = {
  data: EventTraceDataResponse;
};

export const EventTracePlot = ({ data }: EventTracePlotProps) => {
  const plotRef = useRef<HTMLDivElement>(null);

  type RawMemberTrace = {
    member?: string | number | null;
    values?: Array<{ value_time: string; value: number }>;
    trace_points?: Array<{ value_time: string; value: number }>;
  };

  type RawPercentiles = {
    p10?: Array<{ value_time: string; value: number }>;
    p50?: Array<{ value_time: string; value: number }>;
    p90?: Array<{ value_time: string; value: number }>;
  };

  useEffect(() => {
    const currentPlot = plotRef.current;
    if (!currentPlot) return;

    const preInitTraces = data.observed.pre_initialization;
    const postInitTraces = data.observed.post_initialization;
    const dataAny = data as EventTraceDataResponse & {
      forecastMembers?: RawMemberTrace[];
      forecastPercentiles?: RawPercentiles;
    };
    const rawMemberTraces: RawMemberTrace[] =
      dataAny.forecast_members ?? dataAny.forecastMembers ?? [];
    const rawPercentiles: RawPercentiles =
      dataAny.forecast_percentiles ?? dataAny.forecastPercentiles ?? {};

    const forecastPlotData: Plotly.Data[] = rawMemberTraces
      .map((memberTrace, index) => {
        const points = memberTrace.values ?? memberTrace.trace_points ?? [];
        const x = points.map((p) => new Date(p.value_time));
        const y = points.map((p) => Number(p.value));
        if (!x.length || !y.length) {
          return null;
        }

        const showLegend = index === 0;
        const trace = {
          x,
          y,
          type: 'scattergl',
          mode: 'lines',
          name: 'Ensemble Members (Forecast)',
          legendgroup: 'ensemble-members',
          showlegend: showLegend,
          line: { color: '#6f6f6f', width: 1 },
          opacity: 0.35,
          hoverinfo: 'skip',
          meta: String(memberTrace.member ?? 'unknown'),
        };
        return trace as unknown as Plotly.Data;
      })
      .filter((trace): trace is Plotly.Data => trace !== null);

    const buildPercentileTrace = (
      points: Array<{ value_time: string; value: number }> | undefined,
      name: string,
      dash: 'solid' | 'dash'
    ): Plotly.Data | null => {
      if (!points || points.length === 0) {
        return null;
      }

      const x = points.map((p) => new Date(p.value_time));
      const y = points.map((p) => Number(p.value));
      if (!x.length || !y.length) {
        return null;
      }

      return {
        x,
        y,
        type: 'scatter',
        mode: 'lines',
        name,
        line: { color: '#1f77b4', width: 2, dash },
      } as Plotly.ScatterData;
    };

    const percentilePlotData = [
      buildPercentileTrace(rawPercentiles.p10, 'Forecast P10', 'dash'),
      buildPercentileTrace(rawPercentiles.p50, 'Forecast P50', 'solid'),
      buildPercentileTrace(rawPercentiles.p90, 'Forecast P90', 'dash'),
    ].filter((trace): trace is Plotly.Data => trace !== null);

    const plotData: Plotly.Data[] = [
      ...forecastPlotData,
      ...percentilePlotData,
      {
        x: preInitTraces.map((p) => p.value_time),
        y: preInitTraces.map((p) => p.value),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Pre-Initialization (Observed)',
        line: { color: 'black', width: 2 },
        marker: { size: 4 },
      } as Plotly.ScatterData,
      {
        x: postInitTraces.map((p) => p.value_time),
        y: postInitTraces.map((p) => p.value),
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Post-Initialization (Observed)',
        line: { color: 'red', width: 2 },
        marker: { size: 4 },
      } as Plotly.ScatterData,
    ];

    const layout: Partial<Plotly.Layout> = {
      title: {
        text: `Event Trace - Observed vs. Ensemble Forecast<br><sub>${data.primary_location_id} | ${data.configuration_name} | ${data.variable_name} | ${data.threshold}</sub>`,
        font: { size: 14 },
      },
      xaxis: {
        title: { text: 'Date/Time' },
        type: 'date',
      },
      yaxis: {
        title: { text: 'Streamflow (m³/s)' },
      },
      hovermode: 'x unified',
      height: 500,
      margin: { l: 60, r: 60, t: 80, b: 60 },
    };

    void Plotly.newPlot(currentPlot, plotData, layout, { responsive: true, displayModeBar: false });

    return () => {
      if (currentPlot) {
        Plotly.purge(currentPlot);
      }
    };
  }, [data]);

  return <div ref={plotRef} style={{ width: '100%', height: '500px' }} />;
};
