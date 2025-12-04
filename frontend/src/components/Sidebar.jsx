import React from 'react';
import { useLocationSelection } from '../hooks/useDataFetching';

const Sidebar = () => {
  const { selectedLocation } = useLocationSelection();

  return (
    <div className="bg-light border-end h-100">
      <div className="p-3">
        {/* Instructions */}
        <div className="card mb-3">
          <div className="card-header">
            <h6 className="card-title mb-0">🚀 How to Use</h6>
          </div>
          <div className="card-body">
            <div className="small">
              <div className="mb-2">
                <strong>1.</strong> Use the <span className="badge bg-light text-dark">🗺️ Map Filters</span> button on the map to filter locations
              </div>
              <div className="mb-2">
                <strong>2.</strong> Click on a location on the map to select it
              </div>
              <div className="mb-2">
                <strong>3.</strong> Configure timeseries settings and click "Load Timeseries" to view data
              </div>
            </div>
          </div>
        </div>

        {/* Selected Location Info */}
        {selectedLocation && (
          <div className="card">
            <div className="card-header">
              <h6 className="card-title mb-0">📍 Selected Location</h6>
            </div>
            <div className="card-body">
              <div className="mb-2">
                <strong>Name:</strong><br/>
                <span className="text-break">{selectedLocation.name}</span>
              </div>
              <div className="mb-2">
                <strong>ID:</strong><br/>
                <code className="small">{selectedLocation.location_id}</code>
              </div>
              {selectedLocation.coordinates && (
                <div className="small text-muted">
                  <strong>Coordinates:</strong><br/>
                  Lat: {selectedLocation.coordinates[1]?.toFixed(4)}<br/>
                  Lon: {selectedLocation.coordinates[0]?.toFixed(4)}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;