"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { addToWatchlist, removeFromWatchlist } from "@/lib/api";
import type { PricePoint } from "@/hooks/usePriceStream";

interface WatchlistProps {
  tickers: string[];
  prices: Record<string, PricePoint>;
  sparklines: Record<string, number[]>;
  selectedTicker: string;
  onSelect: (ticker: string) => void;
  onWatchlistChange: () => void;
}

function Sparkline({ data }: { data: number[] }) {
  if (data.length < 2) return <div className="w-16 h-8" />;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const width = 64;
  const height = 32;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height;
    return `${x},${y}`;
  });

  const isUp = data[data.length - 1] >= data[0];

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={isUp ? "#3fb950" : "#f85149"}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

function TickerRow({
  ticker,
  priceData,
  sparklineData,
  selected,
  onSelect,
  onRemove,
}: {
  ticker: string;
  priceData?: PricePoint;
  sparklineData: number[];
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}) {
  const priceRef = useRef<HTMLSpanElement>(null);
  // data-testid added for E2E tests
  const prevPrice = useRef<number | null>(null);

  useEffect(() => {
    if (!priceData || !priceRef.current) return;
    if (prevPrice.current === null) {
      prevPrice.current = priceData.price;
      return;
    }
    if (priceData.price === prevPrice.current) return;

    const direction = priceData.price > prevPrice.current ? "up" : "down";
    prevPrice.current = priceData.price;

    const el = priceRef.current;
    el.classList.remove("flash-green", "flash-red");
    // Trigger reflow
    void el.offsetWidth;
    el.classList.add(direction === "up" ? "flash-green" : "flash-red");

    const t = setTimeout(() => {
      el.classList.remove("flash-green", "flash-red");
    }, 700);
    return () => clearTimeout(t);
  }, [priceData?.price]);

  const price = priceData?.price ?? 0;
  const change = priceData?.change ?? 0;
  const changePct = price > 0 ? ((change / (price - change)) * 100) : 0;
  const isUp = change >= 0;

  return (
    <div
      className="flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded"
      style={{
        backgroundColor: selected ? "#1f2937" : "transparent",
        borderLeft: selected ? "2px solid #ecad0a" : "2px solid transparent",
      }}
      onClick={onSelect}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span
            data-testid="ticker-symbol"
            className="text-xs font-bold tracking-wide"
            style={{ fontFamily: "monospace", color: "#e6edf3" }}
          >
            {ticker}
          </span>
          <span
            ref={priceRef}
            data-testid="ticker-price"
            className="text-xs font-mono tabular-nums"
            style={{ color: "#e6edf3" }}
          >
            ${price.toFixed(2)}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <span
            className="text-xs font-mono"
            style={{ color: isUp ? "#3fb950" : "#f85149" }}
          >
            {isUp ? "+" : ""}{changePct.toFixed(2)}%
          </span>
          <Sparkline data={sparklineData} />
        </div>
      </div>
      <button
        data-testid="remove-ticker-btn"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="text-xs px-1 py-0.5 rounded opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity"
        style={{ color: "#484f58" }}
        title="Remove"
      >
        ✕
      </button>
    </div>
  );
}

export function Watchlist({
  tickers,
  prices,
  sparklines,
  selectedTicker,
  onSelect,
  onWatchlistChange,
}: WatchlistProps) {
  const [newTicker, setNewTicker] = useState("");
  const [addError, setAddError] = useState("");
  const [isAdding, setIsAdding] = useState(false);

  const handleAdd = useCallback(async () => {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    setIsAdding(true);
    setAddError("");
    const res = await addToWatchlist(t);
    setIsAdding(false);
    if (res.success) {
      setNewTicker("");
      onWatchlistChange();
    } else {
      setAddError(res.error ?? "Failed to add ticker");
    }
  }, [newTicker, onWatchlistChange]);

  const handleRemove = useCallback(
    async (ticker: string) => {
      await removeFromWatchlist(ticker);
      onWatchlistChange();
    },
    [onWatchlistChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleAdd();
  };

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ borderRight: "1px solid #30363d" }}
    >
      <div
        className="px-3 py-2 text-xs font-semibold uppercase tracking-wider"
        style={{ color: "#8b949e", borderBottom: "1px solid #30363d" }}
      >
        Watchlist
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="py-1">
          {tickers.map((ticker) => (
            <div key={ticker} className="group">
              <TickerRow
                ticker={ticker}
                priceData={prices[ticker]}
                sparklineData={sparklines[ticker] ?? []}
                selected={ticker === selectedTicker}
                onSelect={() => onSelect(ticker)}
                onRemove={() => handleRemove(ticker)}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="p-2" style={{ borderTop: "1px solid #30363d" }}>
        <div className="flex gap-1">
          <input
            data-testid="add-ticker-input"
            type="text"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="Add ticker..."
            className="flex-1 text-xs px-2 py-1 rounded outline-none"
            style={{
              backgroundColor: "#0d1117",
              color: "#e6edf3",
              border: "1px solid #30363d",
              fontFamily: "monospace",
            }}
          />
          <button
            data-testid="add-ticker-btn"
            onClick={handleAdd}
            disabled={isAdding}
            className="text-xs px-2 py-1 rounded font-semibold"
            style={{ backgroundColor: "#209dd7", color: "#fff" }}
          >
            +
          </button>
        </div>
        {addError && (
          <div data-testid="watchlist-error" className="text-xs mt-1" style={{ color: "#f85149" }}>
            {addError}
          </div>
        )}
      </div>
    </div>
  );
}
