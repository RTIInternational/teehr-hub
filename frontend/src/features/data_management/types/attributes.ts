import type { OgcResponse } from '@/shared/types/ogc';

export type AttributesItem = {
  name: string;
  description: string;
  type: string;
  created_at: string;
  updated_at: string;
};

export type AttributesResponse = OgcResponse<AttributesItem>;
