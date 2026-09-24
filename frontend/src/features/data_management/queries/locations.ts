import { skipToken, useQuery } from '@tanstack/react-query';
import type { FeatureCollection, Point } from 'geojson';

import { apiService } from '@/services/api';
import { isPointCollection, isPolygonCollection } from '@/shared/utils/geojson';

export const usePointLocation = (locationId: string | null, name: string | null) =>
  useQuery({
    queryKey: ['location', locationId],
    queryFn: locationId ? () => apiService.getLocationById(locationId) : skipToken,
    select: (data) => {
      if (!isPointCollection(data)) {
        throw new Error('Expected point geometry for usePointLocation');
      }
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
    queryFn: locationId ? () => apiService.getLocationById(locationId) : skipToken,
    select: (data) => {
      if (!isPolygonCollection(data)) {
        throw new Error('Expected polygon geometry for useBasinLocation');
      }
      return data?.features?.length ? data : null;
    },
  });
