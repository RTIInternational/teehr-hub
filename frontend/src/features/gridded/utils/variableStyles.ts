// Per-variable default styling for the gridded map.
// Variables not listed here fall back to DEFAULT_VARIABLE_STYLE.
// Units listed here are used only if the API does not provide them from the
// dataset's variable attributes.
// min is set to a small positive epsilon for accumulation/rate variables so
// that exactly-zero pixels are rendered transparent by the TilesPlugin
// belowmincolor=transparent parameter.

type VariableStyle = {
  colorRamp: string;
  min: number;
  max: number;
  units: string | null;
};

export const DEFAULT_VARIABLE_STYLE: VariableStyle = {
  colorRamp: 'raster/turbo',
  min: 0,
  max: 100,
  units: null,
};

export const VARIABLE_STYLES: Record<string, VariableStyle> = {
  swe_daily_mean: {
    colorRamp: 'raster/turbo',
    min: 0.001,
    max: 100,
    units: 'mm',
  },
  depth_daily_mean: {
    colorRamp: 'raster/turbo',
    min: 0.001,
    max: 100,
    units: 'mm',
  },
  rainrate_hourly_mean: {
    colorRamp: 'raster/turbo',
    min: 0.001,
    max: 0.005,
    units: 'mm/s',
  },
};

export function getVariableStyle(variable: string) {
  return VARIABLE_STYLES[variable] ?? DEFAULT_VARIABLE_STYLE;
}
