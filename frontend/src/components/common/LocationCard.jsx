import React from 'react';
import { Card, CloseButton } from 'react-bootstrap';

const LocationCard = ({ selectedLocation, onClose }) => {
  return (
    <Card 
      className="shadow-sm" 
      style={{ borderRadius: '8px' }}
    >
      <Card.Header className="py-2 px-3 d-flex justify-content-between align-items-center bg-light">
        <div className="d-flex align-items-center flex-grow-1" style={{ minWidth: 0 }}>
          <span style={{ fontSize: '0.9rem' }}>📍</span>
          <span className="ms-2 text-truncate" style={{ fontWeight: selectedLocation ? '600' : 'normal' }}>
            {selectedLocation ? selectedLocation.name : 'Select a Location'}
          </span>
        </div>
        {selectedLocation && (
          <CloseButton 
            size="sm"
            aria-label="Close"
            onClick={onClose}
            className="ms-2"
          />
        )}
      </Card.Header>
    </Card>
  );
};

export default LocationCard;