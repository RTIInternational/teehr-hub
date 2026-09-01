import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

import type { LeadTimeMetricsRow } from '../hooks/useLeadTimeMetrics';
import type { LeadTimeGranularity } from './LeadTimeGranularityToggle';
import { formatConfigurationName } from '../utils/formatConfigurationName';

type LeadTimeMetricChartProps = {
  data: LeadTimeMetricsRow[];
  metricKey: keyof LeadTimeMetricsRow;
  yAxisLabel: string;
  yRangeMode?: 'tozero' | 'normal' | 'nonnegative';
  height?: React.CSSProperties['height'];
  granularity?: LeadTimeGranularity;
};

/**
 * Convert lead time in seconds to total hours.
 */
const secondsToHours = (seconds: number): number => seconds / 3600;

const BASE_COLORS = ['#00a6fb', '#2b5ab4', '#ff7f11', '#2dc653', '#5d2e8c', '#1982c4', '#8a5cf6'];

const LeadTimeMetricChart = ({
  data,
  metricKey,
  yAxisLabel,
  yRangeMode = 'tozero',
  height = '450px',
  granularity = 'daily',
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
      const displayName = formatConfigurationName(configName);

      const toXValue = (r: LeadTimeMetricsRow) =>
        secondsToHours(r.forecast_lead_time as number) / 24;

      traces.push({
        x: rows.map(toXValue),
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
        title: { text: 'Lead Time (days)', font: { size: 11, color: '#395487' } },
        tickfont: { size: 10, color: '#4f6491' },
        showgrid: true,
        gridcolor: '#ebeff8',
        zeroline: false,
        tickmode: 'linear',
        tick0: 1,
        dtick: 1,
        tickformat: 'd',
        rangemode: 'nonnegative',
      },
      yaxis: {
        title: { text: yAxisLabel, font: { size: 11, color: '#395487' } },
        tickfont: { size: 10, color: '#4f6491' },
        showgrid: true,
        gridcolor: '#ebeff8',
        rangemode: yRangeMode,
        zeroline: yRangeMode === 'normal',
        zerolinecolor: '#b5c0d8',
      },
      legend: {
        orientation: 'h',
        yanchor: 'bottom',
        y: -0.28,
        xanchor: 'center',
        x: 0.5,
        font: { size: 10, color: '#334d7f' },
      },
      plot_bgcolor: '#ffffff',
      paper_bgcolor: '#ffffff',
      showlegend: traces.length > 1,
      hovermode: 'x unified',
      hoverlabel: {
        bgcolor: '#0f2c66',
        bordercolor: '#0f2c66',
        font: { color: '#ffffff' },
      },
    };

    void Plotly.react(plotRef.current, traces, layout, {
      displayModeBar: false,
      responsive: true,
    });

    const plotNode = plotRef.current;
    return () => {
      Plotly.purge(plotNode);
    };
  }, [data, metricKey, yAxisLabel, yRangeMode, granularity]);

  return <div ref={plotRef} style={{ width: '100%', height }} />;
};

export default LeadTimeMetricChart;
