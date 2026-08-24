export const getMetricDisplay = (metric) => {
  return metricDisplay[metric];
};

// Helper function to get metric label display name
export const getMetricLabel = (metric) => {
  const display = getMetricDisplay(metric);
  return display?.label || metric;
};

export const getMetricStops = (metric) => {
  const display = getMetricDisplay(metric);
  return display?.stops || undefined;
};

// Helper function for metric color expression
export const getMetricColorExpression = (metric) => {
  if (!metric) return "#0d6efd";

  const display = getMetricDisplay(metric);
  if (!display) return "#0d6efd";

  return [
    "interpolate",
    ["linear"],
    ["get", metric],
    ...display.stops.flatMap((stop, i) => [stop, display.colors[i]]),
  ];
};

const metricDisplay = {
  relative_bias: {
    label: "Relative Bias",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [-1, -0.5, -0.1, 0, 0.1, 0.5, 1],
    stopLabels: [
      "Very Underpredicted",
      "Underpredicted",
      "Slightly Under",
      "No Bias",
      "Slightly Over",
      "Overpredicted",
      "Very Overpredicted",
    ],
  },
  relative_mean: {
    label: "Relative Mean",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [0, 0.5, 0.9, 1, 1.1, 1.5, 2],
    stopLabels: [
      "Much Lower",
      "Lower",
      "Slightly Lower",
      "Near Match",
      "Slightly Higher",
      "Higher",
      "Much Higher",
    ],
  },
  relative_median: {
    label: "Relative Median",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [0, 0.5, 0.9, 1, 1.1, 1.5, 2],
    stopLabels: [
      "Much Lower",
      "Lower",
      "Slightly Lower",
      "Near Match",
      "Slightly Higher",
      "Higher",
      "Much Higher",
    ],
  },
  relative_minimum: {
    label: "Relative Minimum",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [0, 0.5, 0.9, 1, 1.1, 1.5, 2],
    stopLabels: [
      "Much Lower",
      "Lower",
      "Slightly Lower",
      "Near Match",
      "Slightly Higher",
      "Higher",
      "Much Higher",
    ],
  },
  relative_maximum: {
    label: "Relative Maximum",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [0, 0.5, 0.9, 1, 1.1, 1.5, 2],
    stopLabels: [
      "Much Lower",
      "Lower",
      "Slightly Lower",
      "Near Match",
      "Slightly Higher",
      "Higher",
      "Much Higher",
    ],
  },
  relative_standard_deviation: {
    label: "Relative Standard Deviation",
    colors: [
      "#4575b4",
      "#91bfdb",
      "#e0f3f8",
      "#f7f7f7",
      "#fee090",
      "#fc8d59",
      "#d73027",
    ],
    stops: [0, 0.5, 0.9, 1, 1.1, 1.5, 2],
    stopLabels: [
      "Much Less Variable",
      "Less Variable",
      "Slightly Less Variable",
      "Similar Variability",
      "Slightly More Variable",
      "More Variable",
      "Much More Variable",
    ],
  },
  pearson_correlation: {
    label: "Pearson Correlation",
    colors: ["#2166ac", "#92c5de", "#f7f7f7", "#f4a582", "#b2182b"],
    stops: [-1, -0.5, 0, 0.5, 1],
    stopLabels: [
      "Strong Negative",
      "Moderate Negative",
      "No Linear Correlation",
      "Moderate Positive",
      "Strong Positive",
    ],
  },
  nash_sutcliffe_efficiency: {
    label: "Nash-Sutcliffe Efficiency",
    colors: ["#d73027", "#fc8d59", "#91bfdb", "#2166ac"],
    stops: [-1, 0.3, 0.7, 1],
    stopLabels: ["Poor", "Fair", "Good", "Excellent"],
  },
  kling_gupta_efficiency: {
    label: "Kling-Gupta Efficiency",
    colors: ["#d73027", "#fc8d59", "#91bfdb", "#2166ac"],
    stops: [-1, 0.3, 0.7, 1],
    stopLabels: ["Poor", "Fair", "Good", "Excellent"],
  },
  count: {
    label: "Count",
    colors: ["#ffffcc", "#a1dab4", "#41b6c4", "#225ea8"],
    stops: [0, 100, 500, 1000],
    stopLabels: ["Low", "Medium", "High", "Very High"],
  },
  average: {
    label: "Average",
    colors: ["#ffffcc", "#c2e699", "#78c679", "#238443"],
    stops: [0, 1, 5, 20],
    stopLabels: ["Low", "Medium", "High", "Very High"],
  },
};
