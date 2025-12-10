// Shared Map Legend Component - shows color scale for any dashboard
const MapLegend = ({ metric, getMetricLabel }) => {
  if (!metric) return null;
  
  const colorScales = {
    'relative_bias': {
      colors: ['#2166ac', '#5aae61', '#fdd49e', '#d73027'],
      stops: [-1, -0.2, 0.2, 1],
      labels: ['Good', 'Fair', 'Poor', 'Bad']
    },
    'nash_sutcliffe_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1],
      labels: ['Poor', 'Fair', 'Good', 'Excellent']
    },
    'kling_gupta_efficiency': {
      colors: ['#d73027', '#fc8d59', '#91bfdb', '#2166ac'],
      stops: [-1, 0.3, 0.7, 1],
      labels: ['Poor', 'Fair', 'Good', 'Excellent']
    },
    'count': {
      colors: ['#ffffcc', '#a1dab4', '#41b6c4', '#225ea8'],
      stops: [0, 100, 500, 1000],
      labels: ['Low', 'Medium', 'High', 'Very High']
    },
    'average': {
      colors: ['#ffffcc', '#c2e699', '#78c679', '#238443'],
      stops: [0, 1, 5, 20],
      labels: ['Low', 'Medium', 'High', 'Very High']
    }
  };
  
  const scale = colorScales[metric];
  if (!scale) return null;
  
  const metricLabel = getMetricLabel(metric);
  
  return (
    <div 
      className="card position-absolute bottom-0 start-0 m-3 shadow-sm" 
      style={{ minWidth: '150px', maxWidth: '200px', zIndex: 1000, fontSize: '0.85rem' }}
    >
      <div className="card-header py-2">
        <h6 className="card-title mb-0 small">Legend</h6>
      </div>
      <div className="card-body py-2">
        <div className="small"><strong>{metricLabel}</strong></div>
        {scale.colors.map((color, i) => (
          <div key={i} className="d-flex align-items-center mt-1">
            <div 
              style={{
                width: '12px',
                height: '12px',
                backgroundColor: color,
                border: '1px solid #ccc',
                marginRight: '6px'
              }}
            ></div>
            <small>{scale.labels[i]} ({scale.stops[i]})</small>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MapLegend;