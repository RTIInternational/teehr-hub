import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiService } from '@/services/api';
import type {
  ApiKeyItem,
  ApiKeysResponse,
  CreateApiKeyInput,
  CreateApiKeyResponse,
} from '@/shared/types/apiKeys';

export const useApiKeys = () =>
  useQuery<ApiKeysResponse, Error, ApiKeyItem[]>({
    queryKey: ['apiKeys'],
    queryFn: () => apiService.listApiKeys(),
    select: (data) => data?.items || [],
  });

export const useCreateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<CreateApiKeyResponse, Error, CreateApiKeyInput>({
    mutationFn: ({ name, scopes }) => apiService.createApiKey(name, scopes),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};

export const useRevokeApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<null, Error, string>({
    mutationFn: (keyId) => apiService.revokeApiKey(keyId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};
