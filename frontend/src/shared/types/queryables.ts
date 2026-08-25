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

export type TableProperties = {
  metrics: string[];
  group_by: string[];
  description: string;
  allProperties: string[];
};
