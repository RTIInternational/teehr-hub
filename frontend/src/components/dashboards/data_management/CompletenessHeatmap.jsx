import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef, useState } from 'react';
import { apiService } from '../../../services/api';

const CHART_HEIGHT = 700;

const CompletenessHeatmap = ({ configurationName, variableName, unitName }) => {
  const plotRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!configurationName || !variableName || !unitName) return;
    if (!plotRef.current) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiService.getAggregationHuc8Weekly({
      configuration_name: configurationName,
      variable_name: variableName,
      unit_name: unitName,
    }).then((data) => {
      if (cancelled) return;

      const rows = data.items || [];
      if (rows.length === 0) {
        Plotly.purge(plotRef.current);
        return;
      }

      // Normalise values to trimmed strings to avoid type/whitespace mismatches
      const norm = (v) => (v == null ? '' : String(v).trim());

      // Collect unique sorted huc8s and periods
      const periodSet = new Set();
      const huc8Set = new Set();
      rows.forEach((r) => {
        periodSet.add(norm(r.period));
        huc8Set.add(norm(r.spatial_aggregate));
      });
      // Remove any blank keys that came from nulls
      periodSet.delete('');
      huc8Set.delete('');

      const periods = [...periodSet].sort();
      const huc8s = [...huc8Set].sort();

      console.debug('[Heatmap] rows:', rows.length, '| unique huc8s:', huc8s.length, '| unique periods:', periods.length);
      if (rows.length > 0) console.debug('[Heatmap] sample row:', rows[0]);

      // Build lookup using normalised keys
      const lookup = new Map();
      rows.forEach((r) => {
        const h = norm(r.spatial_aggregate);
        const p = norm(r.period);
        if (!h || !p) return;
        const c = r.expected_count > 0
          ? Math.min((r.actual_count / r.expected_count) * 100, 100)
          : null;
        lookup.set(`${h}||${p}`, c);
      });

      // Sort huc8s ascending alphabetically, matching Python's pivot.sort_index()
      const sortedHuc8s = [...huc8s].sort();

      const z = sortedHuc8s.map((h) =>
        periods.map((p) => {
          const v = lookup.get(`${h}||${p}`);
          return v != null ? v : null;
        })
      );

      // Use first 10 chars of period as x-axis label (date portion only)
      const xLabels = periods.map((p) => p.slice(0, 10));

      Plotly.react(
        plotRef.current,
        [
          {
            type: 'heatmap',
            z,
            x: xLabels,
            y: sortedHuc8s,
            zmin: 0,
            zmax: 100,
            colorscale: [
              [0.0, '#d62728'],
              [0.5, '#ffdd57'],
              [1.0, '#2ca02c'],
            ],
            colorbar: { title: 'Completeness (%)' },
            hovertemplate:
              'Spatial Aggregate: %{y}<br>Period: %{x}<br>Completeness: %{z:.1f}%<extra></extra>',
          },
        ],
        {
          title: `Primary Timeseries Completeness — ${configurationName} / ${variableName} (${unitName})`,
          xaxis: { title: 'Week', tickangle: -45, nticks: 24 },
          yaxis: {
            title: 'Spatial Aggregate',
            showticklabels: false,
            type: 'category',
          },
          height: CHART_HEIGHT,
          margin: { l: 40, b: 80, t: 50, r: 20 },
        },
        { responsive: false }
      );
    }).catch((err) => {
      if (!cancelled) setError(err.message);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });

    return () => { cancelled = true; };
  }, [configurationName, variableName, unitName]);

  if (!configurationName || !variableName || !unitName) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted" style={{ minHeight: '120px' }}>
        <span>Select a configuration, variable, and unit above to view completeness.</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-danger m-3">
        <i className="bi bi-exclamation-triangle-fill me-2"></i>
        Failed to load heatmap: {error}
      </div>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {loading && (
        <div
          className="position-absolute top-50 start-50 translate-middle text-center"
          style={{ zIndex: 10 }}
        >
          <div className="spinner-border text-primary mb-2" role="status">
            <span className="visually-hidden">Loading...</span>
          </div>
          <div className="small text-muted">Loading completeness data...</div>
        </div>
      )}
      <div ref={plotRef} style={{ width: '100%', height: `${CHART_HEIGHT}px`, opacity: loading ? 0.3 : 1 }} />
    </div>
  );
};

export default CompletenessHeatmap;
