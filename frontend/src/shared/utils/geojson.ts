import type { FeatureCollection, MultiPolygon, Point, Polygon } from 'geojson';

export const isPointCollection = (data: FeatureCollection): data is FeatureCollection<Point> =>
  data.features.every((feature) => feature.geometry?.type === 'Point');

export const isPolygonCollection = (
  data: FeatureCollection
): data is FeatureCollection<Polygon | MultiPolygon> =>
  data.features.every(
    (feature) => feature.geometry?.type === 'Polygon' || feature.geometry?.type === 'MultiPolygon'
  );
