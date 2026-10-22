import { apiCallJson } from '@/shared/api/client';
import type { OgcResponse } from '@/shared/api/ogc';

export type AttributesItem = {
  name: string;
  description: string;
  type: string;
  created_at: string;
  updated_at: string;
};

export type AttributesResponse = OgcResponse<AttributesItem>;

// Get attribute definitions (name, description, type, updated_at, etc.)
export const getAttributes = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<AttributesResponse>(`/collections/attributes/items?${params.toString()}`);
};
