import { create } from 'zustand';

import type { MapLocation } from '@/shared/types/locations';

interface FiroActions {
  selectLocation: (location: MapLocation | null) => void;
  setError: (error: string) => void;
  clearError: () => void;
  setConfigurationName: (configurationName: string) => void;
  setVariableName: (variableName: string) => void;
}

interface FiroDashboardState {
  // Selected location
  selectedLocation: MapLocation | null;

  // Shared analysis selectors
  selectedConfigurationName: string;
  selectedVariableName: string;

  // Error
  error: string | null;

  // Actions
  actions: FiroActions;
}

export const useFiroDashboardStore = create<FiroDashboardState>()((set) => ({
  // Initial state
  selectedLocation: null,
  selectedConfigurationName: 'hefs_streamflow_forecast',
  selectedVariableName: 'streamflow_hourly_inst',
  error: null,

  // Actions
  actions: {
    selectLocation: (location) => set({ selectedLocation: location }),
    setError: (error) => set({ error }),
    clearError: () => set({ error: null }),
    setConfigurationName: (configurationName) =>
      set({ selectedConfigurationName: configurationName }),
    setVariableName: (variableName) => set({ selectedVariableName: variableName }),
  },
}));

export const useFiroActions = () => useFiroDashboardStore((s) => s.actions);
