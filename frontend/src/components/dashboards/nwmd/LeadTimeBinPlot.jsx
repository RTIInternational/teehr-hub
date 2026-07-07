import Plotly from "plotly.js-dist-min";
import { useEffect, useMemo, useRef } from "react";
import { Card, Spinner } from "react-bootstrap";
import { getMetricLabel } from "../../common/dashboard/utils.js";

const parseDurationToHours = (duration) => {
  if (typeof duration !== "string" || !duration.startsWith("P")) return null;

  const match = duration.match(
    /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/,
  );
  if (!match) return null;

  const days = Number(match[1] || 0);
  const hours = Number(match[2] || 0);
  const minutes = Number(match[3] || 0);
  const seconds = Number(match[4] || 0);

  return days * 24 + hours + minutes / 60 + seconds / 3600;
};

const getMinimumLeadTimeHours = (leadTimeBin) => {
  if (typeof leadTimeBin !== "string") return null;
  const minDuration = leadTimeBin.split("_")[0];
  const hours = parseDurationToHours(minDuration);
  if (hours === null) return null;
  return Math.round(hours);
};

const LeadTimeBinPlot = ({
  selectedLocation,
  mapFilters,
  leadTimeBins = [],
  rows = [],
  loading = false,
  loadLeadTimeBinMetrics,
}) => {
  const plotRef = useRef(null);

  const primaryLocationId = selectedLocation?.primary_location_id;
  const metricName = mapFilters?.metricName;

  useEffect(() => {
    if (!primaryLocationId) {
      return;
    }

    void loadLeadTimeBinMetrics({
      primary_location_id: primaryLocationId,
      configuration: mapFilters?.configuration,
      variable: mapFilters?.variable,
      threshold: mapFilters?.threshold,
      aggMethod: mapFilters?.aggMethod,
    }).catch(() => {
      // Error state is handled in dashboard context.
    });
  }, [
    primaryLocationId,
    mapFilters?.configuration,
    mapFilters?.variable,
    mapFilters?.threshold,
    mapFilters?.aggMethod,
    loadLeadTimeBinMetrics,
  ]);

  const chartData = useMemo(() => {
    if (!metricName || !rows.length) {
      return { x: [], y: [] };
    }

    const grouped = new Map();

    rows.forEach((row) => {
      const bin = row.forecast_lead_time_bin;
      const value = row[metricName];
      if (!bin || value === null || value === undefined) return;
      const numericValue = Number(value);
      if (!Number.isFinite(numericValue)) return;

      const existing = grouped.get(bin) || { sum: 0, count: 0 };
      grouped.set(bin, {
        sum: existing.sum + numericValue,
        count: existing.count + 1,
      });
    });

    const availableBins = Array.isArray(leadTimeBins)
      ? leadTimeBins.filter((bin) => grouped.has(bin))
      : [];
    const fallbackBins = Array.from(grouped.keys()).sort();
    const orderedBins = availableBins.length ? availableBins : fallbackBins;

    const points = orderedBins
      .map((bin) => {
        const item = grouped.get(bin);
        if (!item || item.count === 0) return null;

        const minLeadTimeHours = getMinimumLeadTimeHours(bin);
        if (minLeadTimeHours === null) return null;

        return {
          bin,
          minLeadTimeHours,
          value: item.sum / item.count,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.minLeadTimeHours - b.minLeadTimeHours);

    return {
      x: points.map((point) => point.minLeadTimeHours),
      y: points.map((point) => point.value),
      bins: points.map((point) => point.bin),
    };
  }, [leadTimeBins, metricName, rows]);

  useEffect(() => {
    if (!plotRef.current) return;

    if (!chartData.x.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    const metricLabel = getMetricLabel(metricName || "metric");
    const traces = [
      {
        x: chartData.x,
        y: chartData.y,
        type: "bar",
        marker: {
          color: "#0d6efd",
          line: { color: "#0a58ca", width: 1 },
        },
        customdata: chartData.bins,
        hovertemplate:
          "<b>Minimum Lead Time (h)</b>: %{x}<br>" +
          "<b>Lead Time Bin</b>: %{customdata}<br>" +
          `<b>${metricLabel}</b>: %{y:.4f}<extra></extra>`,
      },
    ];

    const layout = {
      margin: { l: 70, r: 20, t: 20, b: 60 },
      xaxis: {
        title: { text: "Minimum Lead Time (h)" },
        tickangle: -30,
      },
      yaxis: {
        title: { text: metricLabel },
      },
      showlegend: false,
    };

    Plotly.react(plotRef.current, traces, layout, {
      responsive: true,
      displayModeBar: "hover",
    });
  }, [chartData, metricName]);

  return (
    <Card
      className="shadow-lg h-100 d-flex flex-column"
      style={{ borderRadius: "8px" }}
    >
      <Card.Body className="p-2 d-flex flex-column" style={{ minHeight: 0 }}>
        {!primaryLocationId ? (
          <div className="d-flex align-items-center justify-content-center text-muted h-100">
            Select a location to view lead-time metrics.
          </div>
        ) : loading ? (
          <div className="d-flex align-items-center justify-content-center h-100">
            <div className="text-center">
              <Spinner animation="border" size="sm" />
              <div className="small text-muted mt-2">
                Loading lead-time metrics...
              </div>
            </div>
          </div>
        ) : !metricName ? (
          <div className="d-flex align-items-center justify-content-center text-muted h-100">
            Select a metric to view the lead-time bin plot.
          </div>
        ) : !chartData.x.length ? (
          <div className="d-flex align-items-center justify-content-center text-muted h-100">
            No lead-time bin data found for current filters.
          </div>
        ) : (
          <div ref={plotRef} style={{ width: "100%", height: "100%" }} />
        )}
      </Card.Body>
    </Card>
  );
};

export default LeadTimeBinPlot;
