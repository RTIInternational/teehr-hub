import type { AttributesResponse } from '@/features/data_management/types/attributes';
import { apiCallJson } from '@/shared/api/client';

// Get attribute definitions (name, description, type, updated_at, etc.)
export const getAttributes = (limit = 1000, offset = 0) => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  return apiCallJson<AttributesResponse>(`/collections/attributes/items?${params.toString()}`);
};
