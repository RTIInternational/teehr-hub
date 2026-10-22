export type MapLocation = {
  primary_location_id: string;
  secondary_location_id?: string;
  name: string;
  coordinates: [number, number];
};
