import { apiCallJson } from '@/shared/api/client';
import { aliasMap } from '@/shared/api/utils';

export type Queryable = {
  title: string;
  type: string;
  'x-teehr-role'?: string;
  'x-ogc-role'?: string;
};

export type QueryablesResponse = {
  type: string;
  title: string;
  description: string;
  properties: { [key: string]: Queryable };
  'x-teehr-group-by'?: string[];
  'x-teehr-metrics'?: string[];
};

// Get queryables for a collection (OGC API - Features Part 3)
// Returns schema with x-teehr-role extensions for group_by/metric fields
export const getQueryables = (collection = 'sim_metrics_by_location') => {
  return apiCallJson<QueryablesResponse>(`/collections/${collection}/queryables`);
};

// Get distinct values for a queryable property (TEEHR extension)
export const getQueryableValues = (collection: string, propertyName: string) => {
  return apiCallJson<string[]>(`/collections/${collection}/queryables/${propertyName}/values`);
};

// Get distinct values for requested column with optional filters
export const getDistinctValues = async (
  table = 'sim_metrics_by_location',
  columnName: string,
  filters?: Record<string, string>
) => {
  const params = new URLSearchParams();

  for (const key in filters) {
    const paramKey = aliasMap[key] || key;
    const filterValue = filters[key] === null ? 'null' : filters[key];
    if (filterValue) params.append(paramKey, filterValue);
  }

  const paramString = params.toString();
  const endpoint = paramString
    ? `/collections/${table}/queryables/${columnName}/values?${paramString}`
    : `/collections/${table}/queryables/${columnName}/values`;

  return apiCallJson<string[]>(endpoint);
};

// Get table properties (now via queryables endpoint)
export const getTableProperties = (table = 'sim_metrics_by_location') => {
  return apiCallJson(`/collections/${table}/queryables`);
};

// Get table properties for multiple tables in batch
export const getTablePropertiesBatch = async (tables = ['sim_metrics_by_location']) => {
  const results = await Promise.all(
    tables.map((table) => apiCallJson<QueryablesResponse>(`/collections/${table}/queryables`))
  );
  // Return as object keyed by table name
  return tables.reduce<Record<string, QueryablesResponse | null>>((acc, table, idx) => {
    acc[table] = results[idx];
    return acc;
  }, {});
};
