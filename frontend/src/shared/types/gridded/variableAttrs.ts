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

type VariableMetadata = {
  long_name?: string;
  units?: string;
  grid_mapping?: string;
  ['proj:wkt2']?: string;
  ['spatial:dimensions']?: string[];
};
