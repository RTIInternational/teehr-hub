import { useQuery } from '@tanstack/react-query';
import { apiService } from '../../services/api';
import { extractTableProperties } from '../../utils/ogcTransformers';

const fetchTableProperties = async (tables: string[]) => {
  const tableArray = Array.isArray(tables) ? tables : [tables];

  const results = await Promise.all(
    tableArray.map(async (table) => {
      const queryables = await apiService.getQueryables(table);
      return { table, queryables };
    })
  );

  return results;
};

export const useTableProperties = (tables: string[] | string) => {
  const tableArray = Array.isArray(tables) ? tables : [tables];

  return useQuery({
    queryKey: ['tableProperties', [...tableArray].sort()],
    queryFn: () => fetchTableProperties(tableArray),
    select: (results) =>
      Object.fromEntries(
        results.map(({ table, queryables }) => [table, extractTableProperties(queryables)])
      ),
    enabled: tableArray.length > 0,
    staleTime: 60 * 60 * 1000,
  });
};
