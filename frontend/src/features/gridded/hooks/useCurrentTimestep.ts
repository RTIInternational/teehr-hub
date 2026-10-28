import { useTimesteps } from '@/shared/queries/gridded/timesteps';

import { useDashboard } from '../DashboardContext';

// The date the map shows: the active dataset's timestep at the slider position
export const useCurrentTimestep = () => {
  const { state } = useDashboard();
  const { dataset, timestepIndex } = state.mapFilters;
  const timesteps = useTimesteps(dataset);
  return (timesteps.data[timestepIndex] as string | undefined) ?? null;
};
