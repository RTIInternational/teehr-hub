import { Fragment, useMemo } from 'react';

import type { EventHeatmapRow } from '../hooks/useEventHeatmap';

export type TopEventsHeatmapMetric =
  | 'pearson_correlation'
  | 'root_mean_square_error'
  | 'relative_bias';

export type TopEventSummary = {
  eventId: string;
  rank: number;
  peakValue: number;
  label: string;
};

type TopEventsHeatmapProps = {
  data: EventHeatmapRow[];
  topEvents: TopEventSummary[];
  metricKey: TopEventsHeatmapMetric;
  metricLabel: string;
  maxRows?: number;
};

const toNumber = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const lower = trimmed.toLowerCase();
    if (lower === 'null' || lower === 'none' || lower === 'nan') return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const parseDurationHours = (value: string): number | null => {
  const match = value.match(/^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/i);
  if (!match) return null;
  const days = Number(match[1] ?? 0);
  const hours = Number(match[2] ?? 0);
  const minutes = Number(match[3] ?? 0);
  const seconds = Number(match[4] ?? 0);
  return days * 24 + hours + minutes / 60 + seconds / 3600;
};

const leadBinToHours = (leadTimeBin: string): number | null => {
  const parts = leadTimeBin.split('_');
  const upper = parts[parts.length - 1] ?? leadTimeBin;
  return parseDurationHours(upper);
};

const hexToRgb = (hex: string) => {
  const sanitized = hex.replace('#', '');
  const normalized =
    sanitized.length === 3
      ? sanitized
          .split('')
          .map((char) => `${char}${char}`)
          .join('')
      : sanitized;

  return {
    r: Number.parseInt(normalized.slice(0, 2), 16),
    g: Number.parseInt(normalized.slice(2, 4), 16),
    b: Number.parseInt(normalized.slice(4, 6), 16),
  };
};

const interpolateColor = (startHex: string, endHex: string, ratio: number) => {
  const start = hexToRgb(startHex);
  const end = hexToRgb(endHex);
  const clamped = Math.max(0, Math.min(1, ratio));

  return `rgb(${Math.round(start.r + (end.r - start.r) * clamped)}, ${Math.round(start.g + (end.g - start.g) * clamped)}, ${Math.round(start.b + (end.b - start.b) * clamped)})`;
};

const divergingColor = (value: number, maxAbs: number) => {
  if (maxAbs <= 0) return '#f8f9fb';
  if (value === 0) return '#f8f9fb';
  if (value < 0) {
    return interpolateColor('#f8f9fb', '#1f4e8c', Math.abs(value) / maxAbs);
  }
  return interpolateColor('#f8f9fb', '#cc3a2b', value / maxAbs);
};

const sequentialColor = (value: number, min: number, max: number) => {
  const span = max - min;
  const ratio = span <= 0 ? 0.5 : (value - min) / span;
  return interpolateColor('#f7fbff', '#08519c', ratio);
};

const TopEventsHeatmap = ({
  data,
  topEvents,
  metricKey,
  metricLabel,
  maxRows,
}: TopEventsHeatmapProps) => {
  const matrixData = useMemo(() => {
    if (!topEvents.length) {
      return {
        xLabels: [] as string[],
        yLabels: [] as string[],
        z: [] as Array<Array<number | null>>,
      };
    }

    const eventOrder = topEvents.map((event) => event.eventId);
    const eventLabelById = new Map(topEvents.map((event) => [event.eventId, event.label]));
    const eventSet = new Set(eventOrder);

    const bins = new Map<string, number>();
    for (const row of data) {
      if (!eventSet.has(row.event_id)) continue;
      const hours = leadBinToHours(row.forecast_lead_time_bin);
      if (hours === null) continue;
      bins.set(row.forecast_lead_time_bin, hours);
    }

    const sortedBins = [...bins.entries()]
      .sort((a, b) => a[1] - b[1])
      .map(([bin, hours]) => ({ bin, label: `${Math.round(hours)}h` }));

    const valuesByCell = new Map<string, number[]>();
    for (const row of data) {
      if (!eventSet.has(row.event_id)) continue;
      if (!bins.has(row.forecast_lead_time_bin)) continue;
      const value = toNumber(row[metricKey]);
      if (value === null) continue;
      const key = `${row.forecast_lead_time_bin}__${row.event_id}`;
      if (!valuesByCell.has(key)) valuesByCell.set(key, []);
      valuesByCell.get(key)?.push(value);
    }

    const xLabels = eventOrder.map((eventId) => eventLabelById.get(eventId) ?? eventId);
    const visibleBins = maxRows !== undefined ? sortedBins.slice(0, maxRows) : sortedBins;
    const yLabels = visibleBins.map((entry) => entry.label);
    const z = visibleBins.map(({ bin }) =>
      eventOrder.map((eventId) => {
        const key = `${bin}__${eventId}`;
        const values = valuesByCell.get(key);
        if (!values?.length) return null;
        const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
        return Number(avg.toFixed(6));
      })
    );

    return { xLabels, yLabels, z };
  }, [data, maxRows, metricKey, topEvents]);

  const hasMetricValues = useMemo(
    () => matrixData.z.some((row) => row.some((value) => value !== null)),
    [matrixData.z]
  );

  const valueRange = useMemo(() => {
    const values = matrixData.z.flat().filter((value): value is number => value !== null);
    if (!values.length) {
      return { min: 0, max: 1, maxAbs: 1 };
    }

    const min = Math.min(...values);
    const max = Math.max(...values);
    const maxAbs = Math.max(Math.abs(min), Math.abs(max));
    return { min, max, maxAbs };
  }, [matrixData.z]);

  const isDivergingMetric = metricKey === 'relative_bias' || metricKey === 'pearson_correlation';

  const legendLabels = isDivergingMetric
    ? {
        min: `${valueRange.min.toFixed(2)}`,
        mid: '0.00',
        max: `${valueRange.max.toFixed(2)}`,
      }
    : {
        min: `${valueRange.min.toFixed(2)}`,
        mid: `${((valueRange.min + valueRange.max) / 2).toFixed(2)}`,
        max: `${valueRange.max.toFixed(2)}`,
      };

  if (!topEvents.length) {
    return null;
  }

  if (!hasMetricValues) {
    return (
      <div className="firo-empty-state d-flex align-items-center justify-content-center h-100 text-muted">
        <p className="mb-0 small">
          No {metricLabel} values are available for the selected top events.
        </p>
      </div>
    );
  }

  return (
    <div className="firo-heatmap-wrap">
      <div className="firo-heatmap-legend" aria-label={`${metricLabel} color scale`}>
        <span className="firo-heatmap-legend-label">{legendLabels.min}</span>
        <div
          className={`firo-heatmap-legend-bar ${isDivergingMetric ? 'is-diverging' : 'is-sequential'}`}
        >
          <span className="firo-heatmap-legend-midpoint" />
        </div>
        <span className="firo-heatmap-legend-label">{legendLabels.max}</span>
      </div>

      <div
        className="firo-heatmap-grid"
        style={{
          gridTemplateColumns: `76px repeat(${matrixData.xLabels.length}, minmax(40px, 1fr))`,
        }}
      >
        <div className="firo-heatmap-corner" />

        {matrixData.xLabels.map((label, index) => (
          <div key={`x-${label}-${index}`} className="firo-heatmap-x-label" title={label}>
            {label}
          </div>
        ))}

        {matrixData.yLabels.map((rowLabel, rowIndex) => (
          <Fragment key={`row-${rowLabel}-${rowIndex}`}>
            <div key={`y-${rowLabel}-${rowIndex}`} className="firo-heatmap-y-label">
              {rowLabel}
            </div>

            {matrixData.z[rowIndex].map((value, columnIndex) => {
              const backgroundColor =
                value === null
                  ? undefined
                  : isDivergingMetric
                    ? divergingColor(value, valueRange.maxAbs)
                    : sequentialColor(value, valueRange.min, valueRange.max);

              return (
                <div
                  key={`cell-${rowIndex}-${columnIndex}`}
                  className={`firo-heatmap-cell ${value === null ? 'is-missing' : ''}`}
                  style={{ backgroundColor }}
                  title={
                    value === null
                      ? `${matrixData.xLabels[columnIndex]}, ${rowLabel}: missing`
                      : `${matrixData.xLabels[columnIndex]}, ${rowLabel}: ${value.toFixed(4)}`
                  }
                  aria-label={
                    value === null
                      ? `${matrixData.xLabels[columnIndex]}, ${rowLabel}, missing`
                      : `${matrixData.xLabels[columnIndex]}, ${rowLabel}, ${metricLabel} ${value.toFixed(4)}`
                  }
                ></div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
};

export default TopEventsHeatmap;
