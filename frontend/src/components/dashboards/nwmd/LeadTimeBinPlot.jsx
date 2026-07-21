import Plotly from "plotly.js-dist-min";
import { useEffect, useMemo, useRef } from "react";
import { Card, Spinner } from "react-bootstrap";
import { getMetricLabel } from "../../common/dashboard/utils.js";
import { parseDurationToHours } from "./leadTimeBins";

const getMinimumLeadTimeHours = (leadTimeBin) => {
  if (typeof leadTimeBin !== "string") return null;
  const minDuration = leadTimeBin.split("_")[0];
  const hours = parseDurationToHours(minDuration);
  if (hours === null) return null;
  return Math.round(hours);
};

const parseFiniteMetricValue = (value) => {
  if (value === null || value === undefined || value === "") return null;
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : null;
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
  const lowerBoundMetricName = metricName ? `${metricName}_boot_0_025` : null;
  const upperBoundMetricName = metricName ? `${metricName}_boot_0_975` : null;

  useEffect(() => {
    if (!primaryLocationId) {
      return;
    }

    void loadLeadTimeBinMetrics({
      primary_location_id: primaryLocationId,
      quarter: mapFilters?.quarter,
      configuration: mapFilters?.configuration,
      variable: mapFilters?.variable,
      threshold: mapFilters?.threshold,
      aggMethod: mapFilters?.aggMethod,
    }).catch(() => {
      // Error state is handled in dashboard context.
    });
  }, [
    primaryLocationId,
    mapFilters?.quarter,
    mapFilters?.configuration,
    mapFilters?.variable,
    mapFilters?.threshold,
    mapFilters?.aggMethod,
    loadLeadTimeBinMetrics,
  ]);

  const chartData = useMemo(() => {
    if (
      !metricName ||
      !lowerBoundMetricName ||
      !upperBoundMetricName ||
      !rows.length
    ) {
      return { x: [], y: [] };
    }

    const rowsByBin = new Map();

    rows.forEach((row) => {
      const bin = row.forecast_lead_time_bin;
      if (!bin || rowsByBin.has(bin)) {
        if (bin && rowsByBin.has(bin)) {
          console.warn(
            `LeadTimeBinPlot received duplicate rows for lead time bin ${bin}; using the first row only.`,
          );
        }
        return;
      }

      const value = parseFiniteMetricValue(row[metricName]);
      const lowerBound = parseFiniteMetricValue(row[lowerBoundMetricName]);
      const upperBound = parseFiniteMetricValue(row[upperBoundMetricName]);

      if (value === null) {
        return;
      }

      const hasConfidenceInterval = lowerBound !== null && upperBound !== null;

      rowsByBin.set(bin, {
        value,
        lowerBound: hasConfidenceInterval ? lowerBound : null,
        upperBound: hasConfidenceInterval ? upperBound : null,
        hasConfidenceInterval,
      });
    });

    const availableBins = Array.isArray(leadTimeBins)
      ? leadTimeBins.filter((bin) => rowsByBin.has(bin))
      : [];
    const fallbackBins = Array.from(rowsByBin.keys()).sort();
    const orderedBins = availableBins.length ? availableBins : fallbackBins;

    const points = orderedBins
      .map((bin) => {
        const item = rowsByBin.get(bin);
        if (!item) return null;

        const minLeadTimeHours = getMinimumLeadTimeHours(bin);
        if (minLeadTimeHours === null) return null;

        return {
          bin,
          minLeadTimeHours,
          value: item.value,
          lowerBound: item.lowerBound,
          upperBound: item.upperBound,
          hasConfidenceInterval: item.hasConfidenceInterval,
        };
      })
      .filter(Boolean)
      .sort((a, b) => a.minLeadTimeHours - b.minLeadTimeHours);

    const pointsWithCi = points.filter((point) => point.hasConfidenceInterval);
    const pointsWithoutCi = points.filter(
      (point) => !point.hasConfidenceInterval,
    );

    return {
      x: points.map((point) => point.minLeadTimeHours),
      y: points.map((point) => point.value),
      withCi: {
        x: pointsWithCi.map((point) => point.minLeadTimeHours),
        y: pointsWithCi.map((point) => point.value),
        errorUpper: pointsWithCi.map((point) => point.upperBound - point.value),
        errorLower: pointsWithCi.map((point) => point.value - point.lowerBound),
        customdata: pointsWithCi.map((point) => [
          point.bin,
          point.lowerBound,
          point.upperBound,
        ]),
      },
      withoutCi: {
        x: pointsWithoutCi.map((point) => point.minLeadTimeHours),
        y: pointsWithoutCi.map((point) => point.value),
        customdata: pointsWithoutCi.map((point) => [point.bin]),
      },
      customdata: points.map((point) => [
        point.bin,
        point.lowerBound,
        point.upperBound,
      ]),
    };
  }, [
    leadTimeBins,
    lowerBoundMetricName,
    metricName,
    rows,
    upperBoundMetricName,
  ]);

  useEffect(() => {
    if (!plotRef.current) return;

    if (!chartData.x.length) {
      Plotly.purge(plotRef.current);
      return;
    }

    const metricLabel = getMetricLabel(metricName || "metric");
    const traces = [];

    if (chartData.withCi.x.length) {
      traces.push({
        x: chartData.withCi.x,
        y: chartData.withCi.y,
        type: "bar",
        marker: {
          color: "#0d6efd",
          line: { color: "#0a58ca", width: 1 },
        },
        error_y: {
          type: "data",
          array: chartData.withCi.errorUpper,
          arrayminus: chartData.withCi.errorLower,
          color: "#000000",
          thickness: 1,
          width: 6,
        },
        customdata: chartData.withCi.customdata,
        hovertemplate:
          "<b>Minimum Lead Time (h)</b>: %{x}<br>" +
          `<b>${metricLabel}</b>: %{y:.2f}<br>` +
          "<b>95% CI</b>: %{customdata[1]:.2f} -- %{customdata[2]:.2f}<extra></extra>",
      });
    }

    if (chartData.withoutCi.x.length) {
      traces.push({
        x: chartData.withoutCi.x,
        y: chartData.withoutCi.y,
        type: "bar",
        marker: {
          color: "#0d6efd",
          line: { color: "#0a58ca", width: 1 },
        },
        customdata: chartData.withoutCi.customdata,
        hovertemplate:
          "<b>Minimum Lead Time (h)</b>: %{x}<br>" +
          `<b>${metricLabel}</b>: %{y:.2f}<extra></extra>`,
      });
    }

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
