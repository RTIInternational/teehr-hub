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
    legendUrl: 'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_6_10_day_outlk/MapServer/legend?f=json',
    legendLayerId: 1,
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
    id: 'nws-cpc-8-14-day',
    label: 'NWS CPC 8-14 Day Outlook',
    legendUrl: 'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_8_14_day_outlk/MapServer/legend?f=json',
    legendLayerId: 1,
    sourceConfig: {
      type: 'raster',
      tiles: [
        'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_8_14_day_outlk/MapServer/export' +
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
    id: 'nws-cpc-mthly-outlook',
    label: 'NWS CPC Monthly Outlook',
    legendUrl: 'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_mthly_precip_outlk/MapServer/legend?f=json',
    legendLayerId: 0,
    sourceConfig: {
      type: 'raster',
      tiles: [
        'https://mapservices.weather.noaa.gov/vector/rest/services/outlooks/cpc_mthly_precip_outlk/MapServer/export' +
        '?layers=show:0&bbox={bbox-epsg-3857}&bboxSR=3857&size=256,256&imageSR=3857&format=png32&transparent=true&f=image',
      ],
      tileSize: 256,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.7 },
    },
  },
  {
    id: 'smap-l4-surface-soil-moisture',
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
  {
    id: 'smap-l4-root-zone-soil-moisture',
    label: 'SMAP L4 Root Zone Soil Moisture',
    sourceConfig: {
      type: 'raster',
      tiles: [
        'https://gibs-b.earthdata.nasa.gov/wmts/epsg3857/best/' +
        'SMAP_L4_Analyzed_Root_Zone_Soil_Moisture/default/default/' +
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
  {
    id: 'viirs-noaa20-corrected-reflectance-bandsM3-I3-M11',
    label: 'VIIRS NOAA-20 Corrected Reflectance (Bands M3-I3-M11) - False Color (Red Snow)',
    sourceConfig: {
      type: 'raster',
      // TODO: Need to get the latest date for the url below. The current url is hardcoded to 2026-07-07
      tiles: [
        'https://gibs-b.earthdata.nasa.gov/wmts/epsg3857/best/' +
        'VIIRS_NOAA20_CorrectedReflectance_BandsM3-I3-M11/default/2026-07-07/' +
        'GoogleMapsCompatible_Level9/{z}/{y}/{x}.png',
      ],
      tileSize: 256,
      maxzoom: 9,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.75 },
    },
  },
  {
    id: 'viirs-noaa20-corrected-reflectance-bandsM11-I2-I1',
    label: 'VIIRS NOAA-20 Corrected Reflectance (Bands M11-I2-I1) - False Color (Green Veg, Blue Snow)',
    sourceConfig: {
      type: 'raster',
      // TODO: Need to get the latest date for the url below. The current url is hardcoded to 2026-07-07
      tiles: [
        'https://gibs-b.earthdata.nasa.gov/wmts/epsg3857/best/' +
        'VIIRS_NOAA20_CorrectedReflectance_BandsM11-I2-I1/default/2026-07-07/' +
        'GoogleMapsCompatible_Level9/{z}/{y}/{x}.png',
      ],
      tileSize: 256,
      maxzoom: 9,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.75 },
    },
  },
  {
    id: 'viirs-noaa20-corrected-reflectance-truecolor',
    label: 'VIIRS NOAA-20 Corrected Reflectance (True Color)',
    sourceConfig: {
      type: 'raster',
      // TODO: Need to get the latest date for the url below. The current url is hardcoded to 2026-07-07
      tiles: [
        'https://gibs-b.earthdata.nasa.gov/wmts/epsg3857/best/' +
        'VIIRS_NOAA20_CorrectedReflectance_TrueColor/default/2026-07-07/' +
        'GoogleMapsCompatible_Level9/{z}/{y}/{x}.png',
      ],
      tileSize: 256,
      maxzoom: 9,
    },
    layerConfig: {
      type: 'raster',
      paint: { 'raster-opacity': 0.75 },
    },
  },
];
