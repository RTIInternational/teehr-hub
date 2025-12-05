import { Card, Badge } from 'react-bootstrap';
import { useLocationSelection } from '../hooks/useDataFetching';

const Sidebar = () => {
  const { selectedLocation } = useLocationSelection();

  return (
    <div className="bg-light border-end h-100">
      <div className="p-3">
        {/* Instructions */}
        <Card className="mb-3">
          <Card.Header>
            <Card.Title as="h6" className="mb-0">🚀 How to Use</Card.Title>
          </Card.Header>
          <Card.Body>
            <div className="small">
              <div className="mb-2">
                <strong>1.</strong> Use the <Badge bg="light" text="dark">🗺️ Map Filters</Badge> button on the map to filter locations
              </div>
              <div className="mb-2">
                <strong>2.</strong> Click on a location on the map to select it
              </div>
              <div className="mb-2">
                <strong>3.</strong> Configure timeseries settings and click &ldquo;Load Timeseries&rdquo; to view data
              </div>
            </div>
          </Card.Body>
        </Card>

        {/* Selected Location Info */}
        {selectedLocation && (
          <Card>
            <Card.Header>
              <Card.Title as="h6" className="mb-0">📍 Selected Location</Card.Title>
            </Card.Header>
            <Card.Body>
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
            </Card.Body>
          </Card>
        )}
      </div>
    </div>
  );
};

export default Sidebar;