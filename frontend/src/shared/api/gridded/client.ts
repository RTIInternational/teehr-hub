import { ensureFreshToken } from '@/shared/auth/keycloak';

export const GRIDDED_API_BASE_URL =
  import.meta.env.VITE_XPUBLISH_API_BASE_URL || 'http://127.0.0.1:8001';

export const MAX_TIMESERIES_POINTS = 365;

type GriddedApiCall = {
  (path: string, options?: { raw: true }): Promise<string>;
  <T>(path: string, options?: { raw?: false }): Promise<T>;
  <T>(path: string, options: { raw: boolean }): Promise<string | T>;
};

export const griddedApiCall: GriddedApiCall = async <T>(path: string, { raw = false } = {}) => {
  const url = `${GRIDDED_API_BASE_URL}${path}`;
  const token = await ensureFreshToken();
  const headers: HeadersInit = { Accept: raw ? 'text/csv' : 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    throw new Error(`Gridded API error: ${response.status} ${response.statusText}`);
  }
  return raw ? response.text() : (response.json() as T);
};
