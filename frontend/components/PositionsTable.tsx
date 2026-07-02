"use client";

import type { Position } from "@/lib/api";
import type { PricePoint } from "@/hooks/usePriceStream";

interface PositionsTableProps {
  positions: Position[];
  prices: Record<string, PricePoint>;
}

export function PositionsTable({ positions, prices }: PositionsTableProps) {
  const enriched = positions.map((p) => {
    const live = prices[p.ticker];
    const currentPrice = live?.price ?? p.current_price;
    const unrealizedPnl = (currentPrice - p.avg_cost) * p.quantity;
    const pnlPct = p.avg_cost > 0 ? ((currentPrice - p.avg_cost) / p.avg_cost) * 100 : 0;
    return { ...p, currentPrice, unrealizedPnl, pnlPct };
  });

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="px-3 py-2 text-xs font-semibold uppercase tracking-wider"
        style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}
      >
        Positions
      </div>

      {enriched.length === 0 ? (
        <div
          data-testid="no-positions"
          className="flex items-center justify-center flex-1 text-sm"
          style={{ color: "#484f58" }}
        >
          No open positions
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <table className="w-full text-xs" style={{ fontFamily: "monospace" }}>
            <thead>
              <tr style={{ color: "#8b949e", borderBottom: "1px solid #30363d" }}>
                <th className="text-left px-3 py-1.5">Ticker</th>
                <th className="text-right px-2 py-1.5">Qty</th>
                <th className="text-right px-2 py-1.5">Avg Cost</th>
                <th className="text-right px-2 py-1.5">Price</th>
                <th className="text-right px-3 py-1.5">P&amp;L</th>
                <th className="text-right px-3 py-1.5">%</th>
              </tr>
            </thead>
            <tbody>
              {enriched.map((p) => {
                const isProfit = p.unrealizedPnl >= 0;
                const pnlColor = isProfit ? "#3fb950" : "#f85149";
                return (
                  <tr
                    key={p.ticker}
                    data-testid={`position-row-${p.ticker}`}
                    style={{ borderBottom: "1px solid #1f2937" }}
                  >
                    <td
                      className="px-3 py-1.5 font-bold"
                      style={{ color: "#e6edf3" }}
                    >
                      {p.ticker}
                    </td>
                    <td
                      className="text-right px-2 py-1.5 tabular-nums"
                      style={{ color: "#e6edf3" }}
                    >
                      {p.quantity}
                    </td>
                    <td
                      className="text-right px-2 py-1.5 tabular-nums"
                      style={{ color: "#8b949e" }}
                    >
                      ${p.avg_cost.toFixed(2)}
                    </td>
                    <td
                      className="text-right px-2 py-1.5 tabular-nums"
                      style={{ color: "#e6edf3" }}
                    >
                      ${p.currentPrice.toFixed(2)}
                    </td>
                    <td
                      className="text-right px-3 py-1.5 tabular-nums"
                      style={{ color: pnlColor }}
                    >
                      {isProfit ? "+" : ""}${p.unrealizedPnl.toFixed(2)}
                    </td>
                    <td
                      className="text-right px-3 py-1.5 tabular-nums"
                      style={{ color: pnlColor }}
                    >
                      {p.pnlPct >= 0 ? "+" : ""}{p.pnlPct.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
