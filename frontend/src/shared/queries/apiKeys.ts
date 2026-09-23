import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import type { CreateApiKeyInput } from '@/shared/types/apiKeys';

export const useApiKeys = () =>
  useQuery({
    queryKey: ['apiKeys'],
    queryFn: () => apiService.listApiKeys(),
    select: (data) => data?.items || [],
  });

export const useCreateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, scopes }: CreateApiKeyInput) => apiService.createApiKey(name, scopes),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};

export const useRevokeApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (keyId: string) => apiService.revokeApiKey(keyId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};
