// Shared Map Legend Component - shows color scale for any dashboard
import { getMetricDisplay } from "./utils";

const MapLegend = ({ metric, getMetricLabel }) => {
  if (!metric) return null;
  
  const display = getMetricDisplay(metric);
  if (!display) return null;
  
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
        {display.colors.map((color, i) => (
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
            <small>{display.stops[i]}</small>
          </div>
        ))}
      </div>
    </div>
  );
};

export default MapLegend;