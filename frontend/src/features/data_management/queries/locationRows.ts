import { useQuery } from '@tanstack/react-query';

import { apiService } from '@/services/api';
import type { LocationsResponse } from '@/shared/types/locations';

import type {
  LocationAttributesItem,
  LocationAttributesResponse,
} from '../types/locationAttributes';
import type { LocationRow } from '../types/locationRows';

// Pivot EAV rows [{location_id, attribute_name, value}] into a map keyed by location_id
const pivotAttributes = (items: LocationAttributesItem[]) => {
  const map: { [location_id: string]: { [attribute_name: string]: string } } = {};
  (items || []).forEach((item) => {
    if (!map[item.location_id]) map[item.location_id] = {};
    map[item.location_id][item.attribute_name] = item.value;
  });
  return map;
};

export const useLocationRows = (attributes: string[] = []) =>
  useQuery({
    queryKey: ['locationRows', attributes],
    queryFn: () =>
      Promise.all([
        apiService.getLocationIdNames('usgs'),
        apiService.getLocationAttributesByNames(attributes),
      ]),
    select: ([locationsData, attrsData]: [LocationsResponse, LocationAttributesResponse]) => {
      const locItems = locationsData?.items || [];
      const attrItems = attrsData?.items || [];
      const attrMap = pivotAttributes(attrItems);
      const joined: LocationRow[] = locItems.map((loc) => ({
        location_id: loc.id,
        name: loc.name,
        ...attrMap[loc.id],
      }));
      return joined;
    },
  });
