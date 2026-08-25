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
