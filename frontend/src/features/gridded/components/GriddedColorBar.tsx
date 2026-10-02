// Fixed-size vertical color bar for the gridded layer, drawn from the tiles legend JSON so
// its size and position never depend on the value range or label widths.

import type { TilesLegendResponse } from '@/shared/types/gridded/tiles';

type GriddedColorBarProps = {
  legend: TilesLegendResponse;
};

const BAR_WIDTH = 14; // px
const BAR_HEIGHT = 160; // px
const LABEL_WIDTH = 64; // px
const TICK_COUNT = 5;
const GRADIENT_STOPS = 32;

// Exponent form keeps very small values to a fixed label width
const formatTick = (value: number): string =>
  value !== 0 && Math.abs(value) < 1e-3
    ? value.toExponential(2)
    : Number(value.toPrecision(3)).toString();

const GriddedColorBar = ({ legend }: GriddedColorBarProps) => {
  const [min, max] = legend.colorscalerange;
  const { stops } = legend;
  // Unset or 'extend' draws values above the max in the top color
  const topIsOpenEnded = legend.abovemaxcolor == null || legend.abovemaxcolor === 'extend';

  // Sample the legend's stops; plenty for a smooth CSS gradient
  const sampled = Array.from(
    { length: GRADIENT_STOPS },
    (_, i) => stops[Math.round((i / (GRADIENT_STOPS - 1)) * (stops.length - 1))]
  );
  const gradient = `linear-gradient(to top, ${sampled
    .map((s, i) => `${s.color} ${(i / (GRADIENT_STOPS - 1)) * 100}%`)
    .join(', ')})`;
  const ticks = Array.from(
    { length: TICK_COUNT },
    (_, i) => min + (i / (TICK_COUNT - 1)) * (max - min)
  );

  return (
    <div style={{ fontSize: '0.72rem', width: BAR_WIDTH + 6 + LABEL_WIDTH, paddingBlock: '6px' }}>
      {legend.units && <div style={{ fontWeight: 600, marginBottom: '6px' }}>{legend.units}</div>}
      <div className="d-flex" style={{ gap: '6px', height: BAR_HEIGHT }}>
        <div
          style={{
            width: BAR_WIDTH,
            height: BAR_HEIGHT,
            background: gradient,
            border: '1px solid #999',
            flexShrink: 0,
          }}
        />
        <div style={{ position: 'relative', width: LABEL_WIDTH, height: BAR_HEIGHT }}>
          {ticks.map((value, i) => (
            <span
              key={i}
              style={{
                position: 'absolute',
                left: 0,
                bottom: `${(i / (TICK_COUNT - 1)) * 100}%`,
                transform: 'translateY(50%)',
                whiteSpace: 'nowrap',
                lineHeight: 1,
              }}
            >
              {i === TICK_COUNT - 1 && topIsOpenEnded
                ? `≥ ${formatTick(value)}`
                : formatTick(value)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default GriddedColorBar;
