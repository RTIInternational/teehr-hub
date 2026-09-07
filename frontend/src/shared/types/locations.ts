import type { FeatureCollection, Point } from 'geojson';

import type { OgcResponse } from './ogc';

export type LocationMetadataResponse = FeatureCollection<Point>;

export type LocationsItem = {
  id: string;
  name: string;
};

export type LocationsResponse = OgcResponse<LocationsItem>;

export type MapLocation = {
  primary_location_id: string;
  secondary_location_id?: string;
  name: string;
  coordinates: [number, number];
};
