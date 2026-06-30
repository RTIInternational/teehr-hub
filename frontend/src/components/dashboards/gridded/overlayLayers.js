/**
 * Registry of toggleable external overlay layers for the gridded dashboard map.
 *
 * To add a new overlay:
 *   1. Add an entry to OVERLAY_LAYERS with a unique `id`, display `label`,
 *      a MapLibre `sourceConfig` (raster or geojson), and a `layerConfig`.
 *   2. That's it — the overlay will automatically appear as a checkbox in
 *      GriddedControls and be managed by GriddedMapComponent.
 */
export const OVERLAY_LAYERS = [
  {
    id: 'nws-cpc-6-10-day',
    label: 'NWS CPC 6-10 Day Outlook',
    sourceConfig: {
      type: 'raster',
      tiles: [
        'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_6_10_day_outlk/MapServer/export' +
        '?layers=show:1&bbox={bbox-epsg-3857}&bboxSR=3857&size=256,256&imageSR=3857&format=png32&transparent=true&f=image',
      ],
      tileSize: 256,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.7 },
    },
  },
  {
    id: 'smap-l4-soil-moisture',
    label: 'SMAP L4 Surface Soil Moisture',
    sourceConfig: {
      type: 'raster',
      tiles: [
        'https://gibs-b.earthdata.nasa.gov/wmts/epsg3857/best/' +
        'SMAP_L4_Analyzed_Surface_Soil_Moisture/default/default/' +
        'GoogleMapsCompatible_Level6/{z}/{y}/{x}.png',
      ],
      tileSize: 256,
      maxzoom: 6,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.75 },
    },
  },
];
