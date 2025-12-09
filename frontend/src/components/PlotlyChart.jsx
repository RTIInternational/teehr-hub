import Plotly from 'plotly.js-dist-min';
import { useEffect, useRef } from 'react';

// Helper function to format variable names
const formatVariableName = (variableName) => {
  if (!variableName) return 'Value';
  
  // Lookup table for variable name overrides
  const variableLookup = {
    'streamflow_hourly_inst': 'Streamflow (Hourly Instantaneous)',
    'streamflow_daily_mean': 'Streamflow (Daily Mean)',
    'precipitation': 'Precipitation',
    'temperature': 'Temperature',
  };
  
  // Return override if exists, otherwise convert snake_case to Title Case
  return variableLookup[variableName] || 
    variableName
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
};

// Helper function to format unit names
const formatUnitName = (unitName) => {
  if (!unitName) return '';
  
  // Lookup table for unit overrides
  const unitLookup = {
    'm3/s': 'm³/s',
    'm^3/s': 'm³/s',
    'cubic_meters_per_second': 'm³/s',
    'cms': 'm³/s',
    'cfs': 'ft³/s',
    'cubic_feet_per_second': 'ft³/s',
    'deg_c': '°C',
    'celsius': '°C',
    'deg_f': '°F',
    'fahrenheit': '°F',
    'millimeters': 'mm',
    'inches': 'in',
    'meters': 'm',
    'feet': 'ft'
  };
  
  // Return override if exists, otherwise return raw string
  return unitLookup[unitName.toLowerCase()] || unitName;
};

// Helper function to determine y-axis title
const getYAxisTitle = (primaryData, secondaryData, filters) => {
  // Try to get unit from the data first
  let unit = null;
  let variable = null;
  
  if (primaryData?.length > 0 && primaryData[0]?.unit_name) {
    unit = primaryData[0].unit_name;
    variable = primaryData[0].variable_name;
  } else if (secondaryData?.length > 0 && secondaryData[0]?.unit_name) {
    unit = secondaryData[0].unit_name;
    variable = secondaryData[0].variable_name;
  }
  
  // Format the variable and unit names
  const formattedVariable = formatVariableName(variable);
  const formattedUnit = formatUnitName(unit);
  
  // Return formatted title
  if (formattedUnit) {
    return `${formattedVariable} (${formattedUnit})`;
  }
  
  return formattedVariable;
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
            const trace = {
              x: series.timeseries.map(d => d.value_time),
              y: series.timeseries.map(d => d.value),
              name: series.configuration_name,
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