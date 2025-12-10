// Helper function to get metric label display name
export const getMetricLabel = (metric) => {
  const labels = {
    'count': 'Count',
    'average': 'Average',
    'relative_bias': 'Relative Bias',
    'nash_sutcliffe_efficiency': 'Nash-Sutcliffe Efficiency',
    'kling_gupta_efficiency': 'Kling-Gupta Efficiency'
  };
  return labels[metric] || metric;
};