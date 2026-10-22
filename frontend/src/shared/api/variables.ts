import { apiCallJson } from '@/shared/api/client';

// Get variables (distinct variable_name values)
export const getVariables = async (table = 'sim_metrics_by_location') => {
  return apiCallJson<string[]>(`/collections/${table}/queryables/variable_name/values`);
};
