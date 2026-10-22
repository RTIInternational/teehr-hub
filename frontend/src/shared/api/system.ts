import { apiCallJson } from '@/shared/api/client';

// Get available collections (OGC API - Common)
export const getCollections = () => apiCallJson('/collections');

// Get landing page (OGC API - Common)
export const getLandingPage = () => apiCallJson('/');

// Get conformance (OGC API - Common)
export const getConformance = () => apiCallJson('/conformance');

// Health check
export const healthCheck = () => apiCallJson('/health');

// Auth info
export const getMe = () => apiCallJson('/auth/me');
