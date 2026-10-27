// Series colours for timeseries plots
export const SERIES_COLORS = [
  { r: 220, g: 53, b: 69 }, // #dc3545 red
  { r: 40, g: 167, b: 69 }, // #28a745 green
  { r: 255, g: 193, b: 7 }, // #ffc107 yellow
  { r: 23, g: 162, b: 184 }, // #17a2b8 cyan
  { r: 111, g: 66, b: 193 }, // #6f42c1 purple
  { r: 253, g: 126, b: 20 }, // #fd7e14 orange
  { r: 32, g: 201, b: 151 }, // #20c997 teal
];

export const seriesColor = (index: number, opacity = 1) => {
  const { r, g, b } = SERIES_COLORS[index % SERIES_COLORS.length];
  return `rgba(${r}, ${g}, ${b}, ${opacity})`;
};
