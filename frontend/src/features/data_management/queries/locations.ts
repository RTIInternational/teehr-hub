import { useQuery } from '@tanstack/react-query';
import type { FeatureCollection, Point, Polygon } from 'geojson';

import { apiService } from '@/services/api';

export const usePointLocation = (locationId: string | null, name: string | null) =>
  useQuery({
    queryKey: ['location', locationId],
    queryFn: () => apiService.getLocationById(locationId),
    enabled: !!locationId,
    select: (data: FeatureCollection<Point>) => {
      const feature = data?.features?.[0];
      const merged: FeatureCollection<Point> = {
        type: 'FeatureCollection',
        features: [
          {
            ...feature,
            properties: {
              ...feature.properties,
              location_id: locationId,
              name: name,
            },
          },
        ],
      };
      return merged;
    },
  });

export const useBasinLocation = (locationId: string | null) =>
  useQuery({
    queryKey: ['location', locationId],
    queryFn: () => apiService.getLocationById(locationId),
    enabled: !!locationId,
    select: (data: FeatureCollection<Polygon>) => (data?.features?.length ? data : null),
  });
