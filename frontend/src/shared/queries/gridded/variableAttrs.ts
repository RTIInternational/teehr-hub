import { useQuery } from '@tanstack/react-query';
import { griddedApiService } from '../../../services/griddedApi';

const fetchVariableAttrs = async (datasetId?: string | null) => {
  if (!datasetId) {
    throw new Error('Dataset required to retrieve variables');
  }

  return griddedApiService.getGriddedVariableAttrs(datasetId);
};

export const useVariableAttrs = (datasetId?: string | null) =>
  useQuery({
    queryKey: ['gridded', datasetId, 'variableAttrs'],
    queryFn: () => fetchVariableAttrs(datasetId),
    enabled: !!datasetId,
    select: (data) => data.variables,
  });
