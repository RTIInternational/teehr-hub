import { apiCallJson, apiCallVoid } from '@/shared/api/client';

export type ApiKeyItem = {
  id: string;
  name: string;
  scopes: string[];
  created_at: string;
  revoked_at: string | null;
};

export type ApiKeysResponse = {
  items: ApiKeyItem[];
};

export type CreateApiKeyInput = {
  name: string;
  scopes: string[];
};

export type CreateApiKeyResponse = {
  id: string;
  name: string;
  api_key: string;
  scopes: string[];
};

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
