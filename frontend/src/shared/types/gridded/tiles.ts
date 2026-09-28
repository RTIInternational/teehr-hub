export type PolygonFeatures = PolygonFeatureProps[];

export type PolygonFeatureProps = {
  [prop: string]: unknown;
  id: string;
  name: string;
};

export type VectorTile = {
  id: string;
  source_layer: string;
};

export type VectorTilesResponse = {
  items: VectorTile[];
};

// Continuous color legend from the tiles legend endpoint (f=application/json)
export type TilesLegendResponse = {
  colorscalerange: [number, number];
  stops: { value: number; color: string }[];
  units?: string | null;
  abovemaxcolor?: string | null;
};
