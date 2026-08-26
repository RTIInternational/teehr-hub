import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import type { LeadTimeMetricsRow } from '../hooks/useLeadTimeMetrics';

type LeadTimeMetricChartProps = {
  data: LeadTimeMetricsRow[];
  metricKey: keyof LeadTimeMetricsRow;
  yAxisLabel: string;
  yRangeMode?: 'tozero' | 'normal' | 'nonnegative';
  height?: React.CSSProperties['height'];
};

/**
 * Normalize a raw configuration_name to a short display label.
 * Falls back to the raw value for unrecognised strings.
 */
const formatConfigName = (raw: string): string => {
  const lower = raw.toLowerCase();
  if (lower.includes('benchmark')) return 'Benchmark';
  if (lower.includes('hefs')) return 'HEFS';
  return raw;
};

/**
 * Convert lead time in seconds to total hours.
 */
const secondsToHours = (seconds: number): number => seconds / 3600;

// Palette matching the PlotlyChart.tsx secondary trace colors
const BASE_COLORS = [
  '#dc3545', // red
  '#28a745', // green
  '#0d6efd', // blue
  '#ffc107', // yellow
  '#6f42c1', // purple
  '#fd7e14', // orange
  '#20c997', // teal
];

const LeadTimeMetricChart = ({
  data,
  metricKey,
  yAxisLabel,
  yRangeMode = 'tozero',
  height = '450px',
}: LeadTimeMetricChartProps) => {
  const plotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!plotRef.current) return;

    if (!data?.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    // Group rows by configuration_name, keeping only rows with a numeric value for this metric
    const byConfig = new Map<string, LeadTimeMetricsRow[]>();
    for (const row of data) {
      const val = row[metricKey];
      if (val == null || isNaN(Number(val))) continue;
      const cfg = row.configuration_name ?? 'Unknown';
      if (!byConfig.has(cfg)) byConfig.set(cfg, []);
      byConfig.get(cfg)!.push(row);
    }

    // Sort each group by lead time ascending
    byConfig.forEach((rows) =>
      rows.sort((a, b) => (a.forecast_lead_time as number) - (b.forecast_lead_time as number))
    );

    const traces: Partial<Plotly.ScatterData>[] = [];
    let colorIdx = 0;

    [...byConfig.keys()].sort().forEach((configName) => {
      const rows = byConfig.get(configName)!;
      const color = BASE_COLORS[colorIdx % BASE_COLORS.length];
      colorIdx++;
      const displayName = formatConfigName(configName);

      traces.push({
        x: rows.map((r) => secondsToHours(r.forecast_lead_time as number) / 24), // days
        y: rows.map((r) => r[metricKey] as number),
        type: 'scatter',
        mode: 'lines+markers',
        name: displayName,
        line: { color, width: 2.5 },
        marker: { color, size: 5 },
        hovertemplate:
          `<b>${displayName}</b><br>` +
          'Lead Time: %{x}<br>' +
          `${yAxisLabel}: %{y:.4f}<br>` +
          '<extra></extra>',
      });
    });

    const layout: Partial<Plotly.Layout> = {
      margin: { t: 16, r: 16, b: 48, l: 72 },
      xaxis: {
        title: { text: 'Lead Time (days)', font: { size: 11 } },
        tickfont: { size: 10 },
        showgrid: true,
        gridcolor: '#e9ecef',
        zeroline: false,
        tickmode: 'linear',
        tick0: 1,
        dtick: 1,
        tickformat: 'd',
        rangemode: 'nonnegative',
      },
      yaxis: {
        title: { text: yAxisLabel, font: { size: 11 } },
        tickfont: { size: 10 },
        showgrid: true,
        gridcolor: '#e9ecef',
        rangemode: yRangeMode,
        zeroline: yRangeMode === 'normal',
        zerolinecolor: '#adb5bd',
      },
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: -0.28,
        xanchor: 'center',
        x: 0.5,
        font: { size: 10 },
      },
      plot_bgcolor: '#ffffff',
      paper_bgcolor: '#ffffff',
      showlegend: traces.length > 1,
      hovermode: 'x unified',
    };

    void Plotly.react(plotRef.current, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });

    const plotNode = plotRef.current;
    return () => {
      Plotly.purge(plotNode);
    };
  }, [data, metricKey, yAxisLabel, yRangeMode]);

  return <div ref={plotRef} style={{ width: '100%', height }} />;
};

export default LeadTimeMetricChart;
