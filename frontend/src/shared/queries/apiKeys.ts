import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { createApiKey, listApiKeys, revokeApiKey } from '@/shared/api/apiKeys';
import type { CreateApiKeyInput } from '@/shared/types/apiKeys';

export const useApiKeys = () =>
  useQuery({
    queryKey: ['apiKeys'],
    queryFn: () => listApiKeys(),
    select: (data) => data?.items || [],
  });

export const useCreateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, scopes }: CreateApiKeyInput) => createApiKey(name, scopes),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};

export const useRevokeApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (keyId: string) => revokeApiKey(keyId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['apiKeys'] });
    },
  });
};
