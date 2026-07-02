"use client";

import type { Position } from "@/lib/api";

interface PortfolioHeatmapProps {
  positions: Position[];
  totalValue: number;
}

interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
  position: Position;
}

/**
 * Simple slice-and-dice treemap layout algorithm.
 * Divides the container alternating horizontal/vertical splits.
 */
function sliceAndDice(
  items: { value: number; position: Position }[],
  x: number,
  y: number,
  width: number,
  height: number,
  horizontal: boolean
): Rect[] {
  if (items.length === 0) return [];
  if (items.length === 1) {
    return [{ x, y, width, height, position: items[0].position }];
  }

  const total = items.reduce((s, i) => s + i.value, 0);
  const rects: Rect[] = [];
  let offset = 0;

  for (const item of items) {
    const ratio = item.value / total;
    if (horizontal) {
      const w = width * ratio;
      rects.push({ x: x + offset, y, width: w, height, position: item.position });
      offset += w;
    } else {
      const h = height * ratio;
      rects.push({ x, y: y + offset, width, height: h, position: item.position });
      offset += h;
    }
  }

  return rects;
}

function pnlColor(pnlPct: number): string {
  const intensity = Math.min(Math.abs(pnlPct) / 10, 1);
  if (pnlPct >= 0) {
    return `rgba(63, 185, 80, ${0.15 + intensity * 0.55})`;
  }
  return `rgba(248, 81, 73, ${0.15 + intensity * 0.55})`;
}

export function PortfolioHeatmap({ positions, totalValue }: PortfolioHeatmapProps) {
  if (positions.length === 0) {
    return (
      <div
        data-testid="no-positions-heatmap"
        className="flex items-center justify-center h-full text-sm"
        style={{ color: "#484f58" }}
      >
        No positions yet
      </div>
    );
  }

  const items = positions
    .filter((p) => p.quantity > 0)
    .map((p) => ({
      value: Math.max(p.quantity * p.current_price, 1),
      position: p,
    }));

  if (items.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-full text-sm"
        style={{ color: "#484f58" }}
      >
        No positions yet
      </div>
    );
  }

  const W = 300;
  const H = 180;
  const rects = sliceAndDice(items, 0, 0, W, H, true);

  return (
    <div data-testid="portfolio-heatmap" className="flex flex-col h-full overflow-hidden">
      <div
        className="px-3 py-2 text-xs font-semibold uppercase tracking-wider"
        style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}
      >
        Portfolio Heatmap
      </div>
      <div className="flex-1 p-2 overflow-hidden">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          height="100%"
          preserveAspectRatio="none"
        >
          {rects.map(({ x, y, width, height, position }) => (
            <g key={position.ticker}>
              <rect
                x={x + 1}
                y={y + 1}
                width={Math.max(width - 2, 0)}
                height={Math.max(height - 2, 0)}
                fill={pnlColor(position.pnl_pct)}
                rx={2}
                stroke="#30363d"
                strokeWidth={0.5}
              />
              {width > 30 && height > 20 && (
                <>
                  <text
                    x={x + width / 2}
                    y={y + height / 2 - 5}
                    textAnchor="middle"
                    fill="#e6edf3"
                    fontSize={Math.min(14, width / 4)}
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    {position.ticker}
                  </text>
                  <text
                    x={x + width / 2}
                    y={y + height / 2 + 10}
                    textAnchor="middle"
                    fill={position.pnl_pct >= 0 ? "#3fb950" : "#f85149"}
                    fontSize={Math.min(11, width / 5)}
                    fontFamily="monospace"
                  >
                    {position.pnl_pct >= 0 ? "+" : ""}
                    {position.pnl_pct.toFixed(2)}%
                  </text>
                </>
              )}
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}
