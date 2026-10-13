import { useQuery } from '@tanstack/react-query';

// status.json is served from CloudFront outside the cluster (see
// teehr-cloud-platform docs/maintenance-page.md). Unset locally.
const STATUS_URL = import.meta.env.VITE_STATUS_URL;
const REFRESH_MS = 1000 * 60 * 5;

export interface PlatformStatus {
  maintenance: boolean;
  message: string;
}

const fetchPlatformStatus = async (): Promise<PlatformStatus> => {
  const response = await fetch(STATUS_URL, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Status request failed: ${response.status}`);
  }
  return response.json();
};

export const usePlatformStatus = () =>
  useQuery({
    queryKey: ['platformStatus'],
    queryFn: fetchPlatformStatus,
    enabled: Boolean(STATUS_URL),
    staleTime: REFRESH_MS,
    refetchInterval: REFRESH_MS,
    retry: false,
  });
