import { ensureFreshToken, getKeycloak } from '@/features/auth';

import { normalizeEndpoint, normalizeHeaders } from './utils';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
export const API_KEY = import.meta.env.VITE_API_KEY || '';

// Helper function for API calls
export const apiCallJson = async <T>(endpoint: string, options: RequestInit = {}): Promise<T> => {
  try {
    const normalizedEndpoint = normalizeEndpoint(endpoint);
    const url = `${API_BASE_URL}${normalizedEndpoint}`;
    const refreshedToken = await ensureFreshToken();
    const token = refreshedToken || getKeycloak().token || null;
    const { headers: extraHeaders = {}, ...restOptions } = options;
    const authHeaders = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && API_KEY ? { 'X-API-Key': API_KEY } : {}),
    };

    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
        ...authHeaders,
        ...normalizeHeaders(extraHeaders),
      },
      ...restOptions,
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody?.detail ? ` - ${errorBody.detail}` : '';
      } catch {
        detail = '';
      }
      throw new Error(`API Error: ${response.status} ${response.statusText}${detail}`);
    }

    const contentType = (response.headers.get('content-type') || '').toLowerCase();
    if (!contentType.includes('json')) {
      throw new Error(`Expected JSON response, got ${contentType || 'unknown content-type'}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

export const apiCallVoid = async (endpoint: string, options: RequestInit = {}): Promise<void> => {
  try {
    const normalizedEndpoint = normalizeEndpoint(endpoint);
    const url = `${API_BASE_URL}${normalizedEndpoint}`;
    const refreshedToken = await ensureFreshToken();
    const token = refreshedToken || getKeycloak().token || null;
    const { headers: extraHeaders = {}, ...restOptions } = options;
    const authHeaders = {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(!token && API_KEY ? { 'X-API-Key': API_KEY } : {}),
    };

    const response = await fetch(url, {
      headers: {
        ...authHeaders,
        ...normalizeHeaders(extraHeaders),
      },
      ...restOptions,
    });

    if (!response.ok) {
      let detail = '';
      try {
        const errorBody = await response.json();
        detail = errorBody?.detail ? ` - ${errorBody.detail}` : '';
      } catch {
        detail = '';
      }
      throw new Error(`API Error: ${response.status} ${response.statusText}${detail}`);
    }
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};
