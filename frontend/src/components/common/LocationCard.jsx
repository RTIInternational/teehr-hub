import React from 'react';
import { Card, CloseButton } from 'react-bootstrap';

const LocationCard = ({ selectedLocation, onClose }) => {
  if (!selectedLocation) {
    return (
      <Card 
        className="shadow-sm" 
        style={{ borderRadius: '8px', height: '15vh', minHeight: '100px' }}
      >
        <Card.Header className="py-2 px-3 d-flex justify-content-between align-items-center bg-light" style={{ minHeight: '30%' }}>
          <Card.Title as="h6" className="mb-0 text-muted">Location</Card.Title>
        </Card.Header>
        <Card.Body className="d-flex align-items-center justify-content-center text-center text-muted py-2" style={{ flex: '1' }}>
          <div>
            <div style={{ fontSize: '1.5rem' }}>📍</div>
            <small>Select a Location</small>
          </div>
        </Card.Body>
      </Card>
    );
  }

  return (
    <Card 
      className="shadow-sm" 
      style={{ borderRadius: '8px', height: '15vh', minHeight: '100px' }}
    >
      <Card.Header className="py-2 px-3 d-flex justify-content-between align-items-center bg-light" style={{ minHeight: '30%' }}>
        <div className="d-flex align-items-center">
          <span style={{ fontSize: '0.9rem' }}>📍</span>
          <Card.Title as="h6" className="mb-0 ms-2 text-truncate">Selected Location</Card.Title>
        </div>
        <CloseButton 
          size="sm"
          aria-label="Close"
          onClick={onClose}
        />
      </Card.Header>
      <Card.Body className="py-2 px-3" style={{ overflow: 'hidden', flex: '1' }}>
        <div className="text-truncate">
          <strong>{selectedLocation.name}</strong>
        </div>
        <div className="text-muted small text-truncate">
          ID: {selectedLocation.location_id}
        </div>
        {selectedLocation.coordinates && (
          <div className="text-muted small text-truncate">
            {selectedLocation.coordinates[1]?.toFixed(4)}, {selectedLocation.coordinates[0]?.toFixed(4)}
          </div>
        )}
      </Card.Body>
    </Card>
  );
};

export default LocationCard;