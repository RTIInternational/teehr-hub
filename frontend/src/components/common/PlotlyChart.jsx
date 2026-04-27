import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';
import { formatVariableName, formatUnitName, getYAxisTitle } from '../../utils/formatters';

const PlotlyChart = ({ primaryData, secondaryData, selectedLocation, filters, height = '500px' }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const primaryTraces = [];
    const secondaryTraces = [];

    // Primary trace (observations)
    if (primaryData?.length > 0) {
      // Take the first series for primary data
      const primarySeries = primaryData[0];
      if (primarySeries?.timeseries?.length > 0) {
        const configName = primarySeries.configuration_name || 'USGS';
        primaryTraces.push({
          x: primarySeries.timeseries.map(d => d.value_time),
          y: primarySeries.timeseries.map(d => d.value),
          name: 'Observed (' + configName + ')',
          type: 'scatter',
          mode: 'lines',
          line: { color: '#000000', width: 2.5 },
          showlegend: true,
          hovertemplate: 
            '<b>%{fullData.name}</b><br>' +
            'Date: %{x}<br>' +
            `${formatVariableName(primarySeries.variable_name || filters.variable)}: %{y}${primarySeries.unit_name ? ' ' + formatUnitName(primarySeries.unit_name) : ''}<br>` +
            '<extra></extra>'
        });
      }
    }

    // Secondary trace(s) - create a trace for each series
    // Color by configuration_name with opacity varying by reference_time (latest = darkest)
    if (secondaryData?.length > 0) {
      const traceMap = new Map();
      const baseColors = [
        { r: 220, g: 53, b: 69 },   // #dc3545 red
        { r: 40, g: 167, b: 69 },   // #28a745 green
        { r: 255, g: 193, b: 7 },   // #ffc107 yellow
        { r: 23, g: 162, b: 184 },  // #17a2b8 cyan
        { r: 111, g: 66, b: 193 },  // #6f42c1 purple
        { r: 253, g: 126, b: 20 },  // #fd7e14 orange
        { r: 32, g: 201, b: 151 }   // #20c997 teal
      ];
      
      // First pass: group series by configuration_name and collect reference_times
      const configGroups = new Map();
      secondaryData.forEach(series => {
        if (series?.timeseries?.length > 0) {
          const configName = series.configuration_name;
          if (!configGroups.has(configName)) {
            configGroups.set(configName, new Set());
          }
          if (series.reference_time && series.reference_time !== 'null') {
            configGroups.get(configName).add(series.reference_time);
          }
        }
      });
      
      // Assign colors to each configuration and sort reference_times
      const configColorMap = new Map();
      const configRefTimesMap = new Map();
      let colorIndex = 0;
      configGroups.forEach((refTimes, configName) => {
        configColorMap.set(configName, baseColors[colorIndex % baseColors.length]);
        // Sort reference_times oldest to newest
        const sortedRefTimes = Array.from(refTimes).sort((a, b) => new Date(a) - new Date(b));
        configRefTimesMap.set(configName, sortedRefTimes);
        colorIndex++;
      });
      
      // Helper to calculate opacity based on reference_time position
      const getOpacity = (configName, refTime) => {
        const sortedRefTimes = configRefTimesMap.get(configName);
        if (!sortedRefTimes || sortedRefTimes.length <= 1) return 1.0;
        const index = sortedRefTimes.indexOf(refTime);
        if (index === -1) return 1.0;
        // Map from 0.25 (oldest) to 1.0 (newest)
        const minOpacity = 0.25;
        const maxOpacity = 1.0;
        return minOpacity + (index / (sortedRefTimes.length - 1)) * (maxOpacity - minOpacity);
      };
      
      secondaryData.forEach(series => {
        if (series?.timeseries?.length > 0) {
          const key = `${series.configuration_name}|${series.variable_name}|${series.reference_time}`;
          
          if (!traceMap.has(key)) {
            const configName = series.configuration_name;
            
            // Display trace name with reference_time details in hover, but keep legend simple
            let traceName = configName;
            let hoverName = configName;
            if (series.reference_time && series.reference_time !== 'null') {
              // Format reference_time for display (e.g., "2024-01-15T00:00" -> "01/15 00:00")
              try {
                const refDate = new Date(series.reference_time);
                const month = String(refDate.getMonth() + 1).padStart(2, '0');
                const day = String(refDate.getDate()).padStart(2, '0');
                const hours = String(refDate.getHours()).padStart(2, '0');
                const mins = String(refDate.getMinutes()).padStart(2, '0');
                hoverName = `${configName} (${month}/${day} ${hours}:${mins})`;
              } catch {
                hoverName = `${configName} (${series.reference_time})`;
              }
            }
            
            // Get base color for this configuration and calculate opacity
            const baseColor = configColorMap.get(configName) || baseColors[0];
            const opacity = getOpacity(configName, series.reference_time);
            const rgbaColor = `rgba(${baseColor.r}, ${baseColor.g}, ${baseColor.b}, ${opacity})`;
            
            const trace = {
              x: series.timeseries.map(d => d.value_time),
              y: series.timeseries.map(d => d.value),
              name: traceName,
              type: 'scatter',
              mode: 'lines',
              line: { 
                color: rgbaColor, 
                width: 2 
              },
              showlegend: false, // Will be set to true for last occurrence only
              hovertemplate: 
                '<b>' + hoverName + '</b><br>' +
                'Date: %{x}<br>' +
                `${formatVariableName(series.variable_name || filters.variable)}: %{y}${series.unit_name ? ' ' + formatUnitName(series.unit_name) : ''}<br>` +
                (series.reference_time && series.reference_time !== 'null' ? 
                  `Reference: ${series.reference_time}<br>` : '') +
                '<extra></extra>'
            };
            traceMap.set(key, trace);
            secondaryTraces.push(trace);
          }
        }
      });
      
      // Set showlegend only for the last trace of each configuration
      const lastTraceIndexPerConfig = new Map();
      secondaryTraces.forEach((trace, index) => {
        lastTraceIndexPerConfig.set(trace.name, index);
      });
      lastTraceIndexPerConfig.forEach((index) => {
        secondaryTraces[index].showlegend = true;
      });
    }

    // Draw forecasts first and observations last so primary lines remain on top.
    const traces = [...secondaryTraces, ...primaryTraces];

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
      margin: { l: 80, r: 200, t: 20, b: 60 },
      showlegend: true,
      legend: {
        x: 1.01,
        y: 0.95,
        xanchor: 'left',
        yanchor: 'top',
        bgcolor: 'rgba(255, 255, 255, 0.8)',
        bordercolor: '#999',
        borderwidth: 0
      }
    };

    Plotly.react(plotRef.current, traces, layout, { 
      responsive: true,
      displayModeBar: 'hover'
    });

  }, [primaryData, secondaryData, selectedLocation, filters]);

  return <div ref={plotRef} style={{ width: '100%', height }} />;
};

export default PlotlyChart;