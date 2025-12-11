import { useEffect } from 'react';
import { Card } from 'react-bootstrap';
import MetricsTable from './MetricsTable';

const LocationMetrics = ({ 
  selectedLocation, 
  locationMetrics, 
  metricsLoading, 
  error, 
  loadLocationMetrics 
}) => {
  // Load metrics when location is selected
  useEffect(() => {
    if (selectedLocation?.location_id) {
      loadLocationMetrics(selectedLocation.location_id);
    }
  }, [selectedLocation?.location_id, loadLocationMetrics]);

  if (!selectedLocation) {
    return null;
  }

  return (
    <Card className="shadow-lg" style={{ borderRadius: '8px' }}>
      <Card.Header className="py-2 d-flex justify-content-between align-items-center">
        <Card.Title as="h6" className="mb-0">📊 Metrics</Card.Title>
      </Card.Header>
      <Card.Body className="p-0">
        <MetricsTable
          metrics={locationMetrics}
          loading={metricsLoading}
          error={error}
          title="Metrics"
          emptyMessage="No metrics available for this location."
          showTitle={false}
        />
      </Card.Body>
    </Card>
  );
};

export default LocationMetrics;