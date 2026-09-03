import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import { getMetricDisplay, getMetricLabel } from '../../../shared/utils/mapMetrics';
import { useCdfPlot } from './useCdfPlots';

type CdfPlotProps = {
  table: string;
  plotId: string;
};

export const CdfPlot = ({ table, plotId }: CdfPlotProps) => {
  const { cdfData, metricName } = useCdfPlot(table, plotId);
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const metricLabel = getMetricLabel(metricName);
    const display = getMetricDisplay(metricName);

    const trace: Plotly.Data = {
      x: cdfData.map((datum) => datum[0]),
      y: cdfData.map((datum) => datum[1]),
      mode: 'markers',
      type: 'scatter',
    };

    const plotData = [trace];

    const layout: Partial<Plotly.Layout> = {
      xaxis: {
        title: {
          text: metricLabel,
          font: { size: 14 },
        },
        ...(display?.stops
          ? { range: [display.stops.at(0), display.stops.at(-1)] }
          : { rangemode: 'tozero' }),
      },
      yaxis: {
        title: {
          text: 'Empirical CDF',
          font: { size: 14 },
        },
        range: [0, 1.05],
      },
      margin: { l: 80, r: 40, t: 20, b: 40 },
      showlegend: false,
    };

    void Plotly.react(plotRef.current, plotData, layout, {
      responsive: true,
      displayModeBar: 'hover',
    }).catch((error) => {
      console.error('Failed to render CdfPlot', error);
    });
  }, [cdfData, metricName]);

  return <div ref={plotRef} />;
};
