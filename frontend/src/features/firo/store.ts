import { create } from 'zustand';

import type { MapLocation } from '@/shared/types/locations';

interface FiroActions {
  selectLocation: (location: MapLocation | null) => void;
  setError: (error: string) => void;
  clearError: () => void;
}

interface FiroDashboardState {
  // Selected location
  selectedLocation: MapLocation | null;

  // Error
  error: string | null;

  // Actions
  actions: FiroActions;
}

export const useFiroDashboardStore = create<FiroDashboardState>()((set) => ({
  // Initial state
  selectedLocation: null,
  error: null,

  // Actions
  actions: {
    selectLocation: (location) => set({ selectedLocation: location }),
    setError: (error) => set({ error }),
    clearError: () => set({ error: null }),
  },
}));

export const useFiroActions = () => useFiroDashboardStore((s) => s.actions);
