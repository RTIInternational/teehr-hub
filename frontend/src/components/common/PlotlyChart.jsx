import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';
import { formatVariableName, formatUnitName, getYAxisTitle } from '../../utils/formatters';

const PlotlyChart = ({ primaryData, secondaryData, selectedLocation, filters, height = '500px' }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const traces = [];

    // Primary trace (observations)
    if (primaryData?.length > 0) {
      // Take the first series for primary data
      const primarySeries = primaryData[0];
      if (primarySeries?.timeseries?.length > 0) {
        traces.push({
          x: primarySeries.timeseries.map(d => d.value_time),
          y: primarySeries.timeseries.map(d => d.value),
          name: 'Observed (' + (primarySeries.configuration_name || 'USGS') + ')',
          type: 'scatter',
          mode: 'lines',
          line: { color: '#0d6efd', width: 2 },
          hovertemplate: 
            '<b>%{fullData.name}</b><br>' +
            'Date: %{x}<br>' +
            `${formatVariableName(primarySeries.variable_name || filters.variable)}: %{y}${primarySeries.unit_name ? ' ' + formatUnitName(primarySeries.unit_name) : ''}<br>` +
            '<extra></extra>'
        });
      }
    }

    // Secondary trace(s) - create a trace for each series
    if (secondaryData?.length > 0) {
      const traceMap = new Map();
      const colors = ['#dc3545', '#28a745', '#ffc107', '#17a2b8', '#6f42c1', '#fd7e14', '#20c997'];
      let colorIndex = 0;
      
      secondaryData.forEach(series => {
        if (series?.timeseries?.length > 0) {
          const key = `${series.configuration_name}|${series.variable_name}|${series.reference_time}`;
          
          if (!traceMap.has(key)) {
            // Include reference_time in legend name for forecasts (multiple reference_times)
            let traceName = series.configuration_name;
            if (series.reference_time && series.reference_time !== 'null') {
              // Format reference_time for display (e.g., "2024-01-15T00:00" -> "01/15 00:00")
              try {
                const refDate = new Date(series.reference_time);
                const month = String(refDate.getMonth() + 1).padStart(2, '0');
                const day = String(refDate.getDate()).padStart(2, '0');
                const hours = String(refDate.getHours()).padStart(2, '0');
                const mins = String(refDate.getMinutes()).padStart(2, '0');
                traceName = `${series.configuration_name} (${month}/${day} ${hours}:${mins})`;
              } catch {
                traceName = `${series.configuration_name} (${series.reference_time})`;
              }
            }
            
            const trace = {
              x: series.timeseries.map(d => d.value_time),
              y: series.timeseries.map(d => d.value),
              name: traceName,
              type: 'scatter',
              mode: 'lines',
              line: { 
                color: colors[colorIndex % colors.length], 
                width: 2 
              },
              hovertemplate: 
                '<b>%{fullData.name}</b><br>' +
                'Date: %{x}<br>' +
                `${formatVariableName(series.variable_name || filters.variable)}: %{y}${series.unit_name ? ' ' + formatUnitName(series.unit_name) : ''}<br>` +
                (series.reference_time && series.reference_time !== 'null' ? 
                  `Reference: ${series.reference_time}<br>` : '') +
                '<extra></extra>'
            };
            traceMap.set(key, trace);
            traces.push(trace);
            colorIndex++;
          }
        }
      });
    }

    // Only plot if we have traces
    if (traces.length === 0) {
      return;
    }

    const yAxisTitle = getYAxisTitle(primaryData, secondaryData, filters);
    
    const layout = {
      xaxis: { 
        title: {
          text: 'Date',
          font: { size: 14 }
        }
      },
      yaxis: { 
        title: {
          text: yAxisTitle,
          font: { size: 14 }
        }
      },
      margin: { l: 80, r: 20, t: 20, b: 60 },
      showlegend: false
    };

    Plotly.react(plotRef.current, traces, layout, { 
      responsive: true,
      displayModeBar: true
    });

  }, [primaryData, secondaryData, selectedLocation, filters]);

  return <div ref={plotRef} style={{ width: '100%', height }} />;
};

export default PlotlyChart;