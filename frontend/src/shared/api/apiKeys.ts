import { apiCallJson, apiCallVoid } from '@/shared/api/client';
import type { ApiKeysResponse, CreateApiKeyResponse } from '@/shared/types/apiKeys';

// API key management (admin JWT required)
export const listApiKeys = () => apiCallJson<ApiKeysResponse>('/auth/api-keys');

export const createApiKey = (name: string, scopes: string[] = []) =>
  apiCallJson<CreateApiKeyResponse>('/auth/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, scopes }),
  });

export const revokeApiKey = (keyId: string) =>
  apiCallVoid(`/auth/api-keys/${encodeURIComponent(keyId)}`, {
    method: 'DELETE',
  });
