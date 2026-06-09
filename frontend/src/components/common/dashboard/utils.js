// Helper function to get metric label display name
export const getMetricLabel = (metric) => {
  const labels = {
    count: "Count",
    average: "Average",
    relative_bias: "Relative Bias",
    nash_sutcliffe_efficiency: "Nash-Sutcliffe Efficiency",
    kling_gupta_efficiency: "Kling-Gupta Efficiency",
  };
  return labels[metric] || metric;
};

export const metricScales = {
  relative_bias: {
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
    labels: [
      "Very Underpredicted",
      "Underpredicted",
      "Slightly Under",
      "No Bias",
      "Slightly Over",
      "Overpredicted",
      "Very Overpredicted",
    ],
  },
  nash_sutcliffe_efficiency: {
    colors: ["#d73027", "#fc8d59", "#91bfdb", "#2166ac"],
    stops: [-1, 0.3, 0.7, 1],
    labels: ["Poor", "Fair", "Good", "Excellent"],
  },
  kling_gupta_efficiency: {
    colors: ["#d73027", "#fc8d59", "#91bfdb", "#2166ac"],
    stops: [-1, 0.3, 0.7, 1],
    labels: ["Poor", "Fair", "Good", "Excellent"],
  },
  count: {
    colors: ["#ffffcc", "#a1dab4", "#41b6c4", "#225ea8"],
    stops: [0, 100, 500, 1000],
    labels: ["Low", "Medium", "High", "Very High"],
  },
  average: {
    colors: ["#ffffcc", "#c2e699", "#78c679", "#238443"],
    stops: [0, 1, 5, 20],
    labels: ["Low", "Medium", "High", "Very High"],
  },
};
