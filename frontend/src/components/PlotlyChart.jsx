import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

// Helper function to determine y-axis title
const getYAxisTitle = (primaryData, secondaryData, filters) => {
  // Try to get unit from the data first
  let unit = null;
  let variable = null;
  
  if (primaryData?.length > 0 && primaryData[0]?.unit_name) {
    unit = primaryData[0].unit_name;
    variable = primaryData[0].variable_name || filters.variable;
  } else if (secondaryData?.length > 0 && secondaryData[0]?.unit_name) {
    unit = secondaryData[0].unit_name;
    variable = secondaryData[0].variable_name || filters.variable;
  }
  
  // If we have a unit from the data, use it
  if (unit) {
    return variable ? `${variable} (${unit})` : `Value (${unit})`;
  }
  
  // Fallback to predefined units based on variable name
  const variable_name = variable || filters.variable;
  const units = {
    'streamflow_hourly_inst': 'Streamflow (m³/s)',
    'streamflow_daily_mean': 'Streamflow (m³/s)', 
    'precipitation': 'Precipitation (mm)',
    'temperature': 'Temperature (°C)'
  };
  
  return units[variable_name] || (variable_name ? variable_name : 'Value');
};

const PlotlyChart = ({ primaryData, secondaryData, selectedLocation, filters }) => {
  const plotRef = useRef(null);

  useEffect(() => {
    if (!plotRef.current) return;

    const traces = [];

    // Primary trace
    if (primaryData?.length > 0) {
      // Take the first series for primary data
      const primarySeries = primaryData[0];
      if (primarySeries?.timeseries?.length > 0) {
        traces.push({
          x: primarySeries.timeseries.map(d => d.value_time),
          y: primarySeries.timeseries.map(d => d.value),
          name: primarySeries.configuration_name || filters.configuration,
          type: 'scatter',
          mode: 'lines',
          line: { color: '#0d6efd', width: 2 }
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
            const trace = {
              x: series.timeseries.map(d => d.value_time),
              y: series.timeseries.map(d => d.value),
              name: series.configuration_name,
              type: 'scatter',
              mode: 'lines',
              line: { 
                color: colors[colorIndex % colors.length], 
                width: 2 
              }
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
      showlegend: true
    };

    Plotly.react(plotRef.current, traces, layout, { 
      responsive: true,
      displayModeBar: true
    });

    // Window resize handler
    // const handleResize = () => {
    //   if (plotRef.current) {
    //     Plotly.Plots.resize(plotRef.current);
    //   }
    // };
    
    // window.addEventListener('resize', handleResize);

    // Cleanup
    // return () => {
    //   window.removeEventListener('resize', handleResize);
    //   if (plotRef.current) {
    //     Plotly.purge(plotRef.current);
    //   }
    // };
  }, [primaryData, secondaryData, selectedLocation, filters]);

  return <div ref={plotRef} style={{ width: '100%', height: '500px' }} />;
};

export default PlotlyChart;