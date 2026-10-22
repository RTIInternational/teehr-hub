import { queryOptions, useQuery } from '@tanstack/react-query';

import { getDistinctValues } from '@/shared/api/queryables';

export const distinctValuesQuery = (
  table: string,
  columnName: string,
  filters?: Record<string, string>
) =>
  queryOptions({
    queryKey: ['distinctValues', table, columnName, filters],
    queryFn: () => getDistinctValues(table, columnName, filters),
  });

export const useDistinctValues = (
  table: string,
  columnName: string,
  filters?: Record<string, string>
) => useQuery(distinctValuesQuery(table, columnName, filters));
