import type { OgcResponse } from '@/shared/types/ogc';

export type LocationAttributesItem = {
  location_id: string;
  attribute_name: string;
  value: string;
  created_at: string;
  updated_at: string;
  properties: { [key: string]: string };
};

export type LocationAttributesResponse = OgcResponse<LocationAttributesItem>;
