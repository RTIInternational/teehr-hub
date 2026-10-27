export type ClickedPoint = {
  lon: number;
  lat: number;
};

// A point query: where the map was clicked and the date it showed
export type PointQuery = ClickedPoint & { time: string };

// A polygon query: the location loaded from the polygon panel and the map's date then
export type PolygonQuery = { location_id: string; name: string; time: string };

export type MapFilters = {
  dataset: string | null;
  variable: string | null;
  timestepIndex: number;
  colorRamp: string;
  colorRampMin: number;
  colorRampMax: number;
};

export type SelectedLocation = {
  primary_location_id: string;
  name: string;
  coordinates: number[] | null;
};
