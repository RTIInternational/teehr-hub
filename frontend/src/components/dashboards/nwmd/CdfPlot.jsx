import Plotly from "plotly.js-dist-min";
import { useEffect, useRef } from "react";

export const CdfPlot = ({ metricLabel, cdfData }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

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
        rangemode: "tozero",
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
  }, [cdfData, metricLabel]);

  return <div ref={plotRef} />;
};
