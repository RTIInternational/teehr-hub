import { griddedApiCall } from './client';

export type VariableAttrsResponse = {
  dataset_id: string;
  variables: VariableAttrs;
};

export type VariableAttrs = Record<string, VariableMetadata> & { crs: CrsMetadata };

type CrsMetadata = {
  crs_wkt: string;
  semi_major_axis: number;
  semi_minor_axis: number;
  inverse_flattening: number;
  reference_ellipsoid_name: string;
  longitude_of_prime_meridian: number;
  prime_meridian_name: string;
  geographic_crs_name: string;
  horizontal_datum_name: string;
  grid_mapping_name: string;
  spatial_ref: string;
};

export type VariableMetadata = {
  long_name?: string;
  units?: string;
  grid_mapping?: string;
  ['proj:wkt2']?: string;
  ['spatial:dimensions']?: string[];
  // teehr's name and units for the variable, and the conversion from its stored values (set on ingest)
  ['teehr:variable_name']?: string;
  ['teehr:unit_name']?: string;
  ['teehr:scale']?: number;
  ['teehr:offset']?: number;
};

export type TeehrMapping = {
  variable: string;
  units: string | null;
  toDisplay: (value: number) => number;
  fromDisplay: (value: number) => number;
};

// How a dataset's variable is shown: teehr's name, units and values from its teehr:* attributes,
// else its own name and units, unconverted (e.g. a repo ingested before them, or an external one)
export const teehrMapping = (variable: string, attrs?: VariableMetadata): TeehrMapping => {
  const scale = attrs?.['teehr:scale'] ?? 1;
  const offset = attrs?.['teehr:offset'] ?? 0;
  return {
    variable: attrs?.['teehr:variable_name'] ?? variable,
    units: attrs?.['teehr:unit_name'] ?? attrs?.units ?? null,
    toDisplay: (value) => value * scale + offset,
    fromDisplay: (value) => (value - offset) / scale,
  };
};

export const getGriddedVariableAttrs = (datasetId: string) =>
  griddedApiCall<VariableAttrsResponse>(
    `/api/datasets/${encodeURIComponent(datasetId)}/variable-attrs`
  );
