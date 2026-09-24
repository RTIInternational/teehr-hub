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
