import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import type { EventTraceDataResponse } from '../hooks/useEventTraceInitializations';

type EventTraceObservedPlotProps = {
  data: EventTraceDataResponse;
};

export const EventTraceObservedPlot = ({ data }: EventTraceObservedPlotProps) => {
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const preInitTraces = data.observed.pre_initialization;
    const postInitTraces = data.observed.post_initialization;

    const plotData: Plotly.Data[] = [
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
        text: `Event Trace - Observed Data<br><sub>${data.primary_location_id} | ${data.configuration_name} | ${data.variable_name} | ${data.threshold}</sub>`,
        font: { size: 14 },
      },
      xaxis: {
        title: { text: 'Valid Time' },
        type: 'date',
      },
      yaxis: {
        title: { text: data.variable_name },
      },
      hovermode: 'x unified',
      height: 500,
      margin: { l: 60, r: 60, t: 80, b: 60 },
    };

    Plotly.newPlot(plotRef.current, plotData, layout, { responsive: true, displayModeBar: false });

    return () => {
      if (plotRef.current) {
        Plotly.purge(plotRef.current);
      }
    };
  }, [data]);

  return <div ref={plotRef} style={{ width: '100%', height: '500px' }} />;
};
