import { useCallback, useReducer } from 'react';
import Button from 'react-bootstrap/Button';
import Card from 'react-bootstrap/Card';

import type { MapLocation } from '@/shared/types/locations';

import { useLocationSelection } from '../hooks/useLocationSelection';
import FiroLocationsMap from './FiroLocationsMap';

// ─── Location detail panel ────────────────────────────────────────────────────

type LocationDetailProps = {
  candidate: MapLocation | null;
  onConfirm: () => void;
  onClear: () => void;
};

const LocationDetail = ({ candidate, onConfirm, onClear }: LocationDetailProps) => (
  <div className="d-flex flex-column h-100">
    <div className="px-3 pt-3 pb-2 border-bottom">
      <span className="text-uppercase fw-semibold firo-location-panel-title">
        Selected Location
      </span>
    </div>

    {candidate ? (
      <>
        <div className="flex-grow-1 p-3">
          <Card className="firo-location-detail-card bg-white">
            <Card.Body className="p-3">
              <p className="fw-semibold mb-1" style={{ fontSize: '0.95rem' }}>
                {candidate.name}
              </p>
              <p className="text-muted mb-1 small">
                <span className="fw-medium">ID: </span>
                {candidate.primary_location_id}
              </p>
              {candidate.secondary_location_id && (
                <p className="text-muted mb-1 small">
                  <span className="fw-medium">Secondary ID: </span>
                  {candidate.secondary_location_id}
                </p>
              )}
              <p className="text-muted mb-0 small">
                <span className="fw-medium">Coordinates: </span>
                {candidate.coordinates[1].toFixed(4)}°N, {candidate.coordinates[0].toFixed(4)}°W
              </p>
            </Card.Body>
          </Card>
        </div>

        <div className="p-3 border-top d-flex flex-column gap-2">
          <Button variant="primary" className="w-100 firo-primary-btn" onClick={onConfirm}>
            Continue to Analysis
          </Button>
          <Button
            variant="outline-secondary"
            size="sm"
            className="w-100 firo-secondary-btn"
            onClick={onClear}
          >
            Clear Selection
          </Button>
        </div>
      </>
    ) : (
      <div className="firo-empty-state flex-grow-1 d-flex flex-column align-items-center justify-content-center p-3 text-center text-muted">
        <p className="mb-0 small">Click a location on the map to select it.</p>
      </div>
    )}
  </div>
);

// ─── Section ──────────────────────────────────────────────────────────────────

export const LocationSelectionSection = () => {
  const { confirmLocation } = useLocationSelection();

  // Local state for the map-clicked candidate — separate from the confirmed
  // store selection so the user must explicitly press "Continue to Analysis".
  const [candidate, setCandidate] = useReducer(
    (_prev: MapLocation | null, next: MapLocation | null) => next,
    null
  );

  const handleConfirm = useCallback(() => {
    if (!candidate) return;
    confirmLocation(candidate);
  }, [candidate, confirmLocation]);

  const handleClear = useCallback(() => {
    setCandidate(null);
  }, []);

  return (
    <div className="firo-location-layout">
      {/* Map — fills available space */}
      <div className="firo-map-pane flex-grow-1 position-relative">
        <FiroLocationsMap selectedLocation={candidate} onSelectLocation={setCandidate} />
      </div>

      {/* Right detail panel */}
      <div className="firo-location-panel d-flex flex-column">
        <LocationDetail candidate={candidate} onConfirm={handleConfirm} onClear={handleClear} />
      </div>
    </div>
  );
};
