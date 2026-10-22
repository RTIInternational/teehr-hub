import type { FeatureCollection, Point } from 'geojson';

import { apiCallJson } from '@/shared/api/client';
import type { OgcResponse } from '@/shared/api/ogc';

export type LocationMetadataResponse = FeatureCollection;

export type LocationsItem = {
  id: string;
  name: string;
};

export type LocationsResponse = OgcResponse<LocationsItem>;

export type LocationAttributesItem = {
  location_id: string;
  attribute_name: string;
  value: string;
  created_at: string;
  updated_at: string;
  properties: { [key: string]: string };
};

export type LocationAttributesResponse = OgcResponse<LocationAttributesItem>;

// Get all locations (OGC API - Features)
export const getLocations = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<OgcResponse<FeatureCollection>>(
    `/collections/locations/items?${params.toString()}`
  );
};

// Get location id + name (no geometry) filtered by prefix, returns {items: [{id, name}]}
export const getLocationIdNames = (prefix: string, limit: number | null = null) => {
  const params = new URLSearchParams();
  if (prefix) params.append('prefix', prefix);
  params.append('include_geometry', 'false');
  if (limit != null) params.append('limit', limit.toString());
  return apiCallJson<LocationsResponse>(`/collections/locations/items?${params.toString()}`);
};

// Get location attributes for specified attribute names (EAV rows, one per location+name)
// Returns {items: [{location_id, attribute_name, value}, ...]}
export const getLocationAttributesByNames = (attributeNames: string[] = [], limit = null) => {
  const params = new URLSearchParams();
  attributeNames.forEach((name) => params.append('attribute_name', name));
  if (limit != null) params.append('limit', limit);
  return apiCallJson<LocationAttributesResponse>(
    `/collections/location_attributes/items?${params.toString()}`
  );
};

// Get a single location by id from the locations table
// Returns a GeoJSON FeatureCollection with the matching feature
export const getLocationById = (id: string, includeAttributes = false) => {
  const params = new URLSearchParams();
  params.append('id', id);
  params.append('limit', '1');
  params.append('include_attributes', includeAttributes.toString());
  return apiCallJson<LocationMetadataResponse>(`/collections/locations/items?${params.toString()}`);
};

// Get GeoJSON for all locations matching a configuration + variable
export const getConfigurationLocationsGeojson = (
  filters: { configuration_name?: string; variable_name?: string; limit?: number } = {}
) => {
  const params = new URLSearchParams();
  if (filters.configuration_name) params.append('configuration_name', filters.configuration_name);
  if (filters.variable_name) params.append('variable_name', filters.variable_name);
  params.append('f', 'geojson');
  params.append('limit', filters.limit?.toString() ?? '50000');
  return apiCallJson<FeatureCollection<Point>>(
    `/collections/configurations_by_location/items?${params.toString()}`
  );
};
