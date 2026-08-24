import Plotly from "plotly.js-dist-min";
import { useEffect, useRef } from "react";
import { getMetricDisplay, getMetricLabel } from "../../common/dashboard/utils";
import { useCdfPlot } from "./useCdfPlots";

export const CdfPlot = ({ plotId }) => {
  const { cdfData, metricName } = useCdfPlot(plotId);
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const metricLabel = getMetricLabel(metricName);
    const display = getMetricDisplay(metricName);

    const trace = {
      x: cdfData.map((datum) => datum[0]),
      y: cdfData.map((datum) => datum[1]),
      mode: "markers",
      type: "scatter",
    };

    const plotData = [trace];

    const layout = {
      xaxis: {
        title: {
          text: metricLabel,
          font: { size: 14 },
        },
        ...(display?.stops
          ? { range: [display.stops.at(0), display.stops.at(-1)] }
          : { rangemode: "tozero" }),
      },
      yaxis: {
        title: {
          text: "Empirical CDF",
          font: { size: 14 },
        },
        range: [0, 1.05],
      },
      margin: { l: 80, r: 40, t: 20, b: 40 },
      showlegend: false,
    };

    Plotly.react(plotRef.current, plotData, layout, {
      responsive: true,
      displayModeBar: "hover",
    });
  }, [cdfData, metricName]);

  return <div ref={plotRef} />;
};
