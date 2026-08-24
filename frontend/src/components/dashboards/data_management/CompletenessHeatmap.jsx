import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef, useState } from 'react';
import { apiService } from '../../../services/api';

const CompletenessHeatmap = ({ configurationName, variableName, onHover = null }) => {
  const plotRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [plotReady, setPlotReady] = useState(false);

  useEffect(() => {
    if (!configurationName || !variableName) return;
    if (!plotRef.current) return;

    let cancelled = false;
    const loadHeatmap = async () => {
      setLoading(true);
      setError(null);
      setPlotReady(false);

      try {
        const data = await apiService.getCompletenessHeatmap({
          configuration_name: configurationName,
          variable_name: variableName,
        });

        if (cancelled) return;

        const rows = data.items || [];
        if (rows.length === 0) {
          Plotly.purge(plotRef.current);
          setPlotReady(false);
          return;
        }

        // Normalise values to trimmed strings to avoid type/whitespace mismatches
        const norm = (v) => (v == null ? '' : String(v).trim());

        // Collect unique sorted aggregation units and periods
        const periodSet = new Set();
        const spatialAggregateSet = new Set();
        rows.forEach((r) => {
          periodSet.add(norm(r.period));
          spatialAggregateSet.add(norm(r.spatial_aggregate));
        });
        // Remove any blank keys that came from nulls
        periodSet.delete('');
        spatialAggregateSet.delete('');

        const periods = [...periodSet].sort();
        const spatialAggregates = [...spatialAggregateSet].sort();

        console.debug('[Heatmap] rows:', rows.length, '| unique spatial aggregates:', spatialAggregates.length, '| unique periods:', periods.length);
        if (rows.length > 0) console.debug('[Heatmap] sample row:', rows[0]);

        // Build lookup using normalised keys
        const lookup = new Map();
        rows.forEach((r) => {
          const h = norm(r.spatial_aggregate);
          const p = norm(r.period);
          if (!h || !p) return;
          const c = r.completeness != null ? r.completeness : null;
          lookup.set(`${h}||${p}`, c);
        });

        // Sort spatial aggregates ascending alphabetically
        const sortedSpatialAggregates = [...spatialAggregates].sort();

        const z = sortedSpatialAggregates.map((h) =>
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
              y: sortedSpatialAggregates,
              zmin: 0,
              zmax: 100,
              colorscale: [
                  [0.0,  '#fd0de9'],
                  [0.2,  '#ca0ef3'],
                  [0.4,  '#970ef9'],
                  [0.6,  '#640efc'],
                  [0.8,  '#380ffd'],
                  [1.0,  '#0d6efd'],
              ],
              colorbar: { title: 'Completeness (%)' },
              opacity: 0.85,
              hovertemplate:
                'Spatial Aggregate: %{y}<br>Period: %{x}<br>Completeness: %{z:.1f}%<extra></extra>',
            },
          ],
          {
            title: `Primary Timeseries Completeness — ${configurationName} / ${variableName}`,
            xaxis: { title: 'Week', tickangle: -45, nticks: 24 },
            yaxis: {
              title: { text: 'Spatial Aggregate', standoff: 8 },
              showticklabels: false,
              type: 'category',
            },
            autosize: true,
            margin: { l: 60, b: 80, t: 50, r: 20 },
          },
          { responsive: true }
        );
        if (!cancelled) setPlotReady(true);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadHeatmap();

    return () => {
      cancelled = true;
      if (onHover) onHover(null);
    };
  }, [configurationName, variableName, onHover]);

  // Attach Plotly hover events once the plot is rendered
  useEffect(() => {
    if (!plotReady || !plotRef.current) return;
    const el = plotRef.current;
    const handleHover = (data) => {
      if (onHover && data.points?.[0]) onHover(String(data.points[0].y));
    };
    const handleUnhover = () => { if (onHover) onHover(null); };
    el.on('plotly_hover', handleHover);
    el.on('plotly_unhover', handleUnhover);
    return () => {
      el.removeListener?.('plotly_hover', handleHover);
      el.removeListener?.('plotly_unhover', handleUnhover);
    };
  }, [plotReady, onHover]);

  if (!configurationName || !variableName) {
    return (
      <div className="d-flex align-items-center justify-content-center h-100 text-muted" style={{ minHeight: '120px' }}>
        <span>Select a configuration and variable above to view completeness.</span>
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
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
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
      <div ref={plotRef} style={{ width: '100%', height: '100%', opacity: loading ? 0.3 : 1 }} />
    </div>
  );
};

export default CompletenessHeatmap;
