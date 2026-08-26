import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import type { MapLocation } from '@/shared/types/locations';

import { useFiroActions } from '../store';

/**
 * Wraps the store's selectLocation action and automatically advances the
 * workflow to the Detailed Analysis section once a location is confirmed.
 */
export const useLocationSelection = () => {
  const { selectLocation } = useFiroActions();
  const navigate = useNavigate();

  const confirmLocation = useCallback(
    (location: MapLocation) => {
      selectLocation(location);
      navigate('/firo/detailed-analysis/deterministic');
    },
    [selectLocation, navigate]
  );

  return { confirmLocation };
};
