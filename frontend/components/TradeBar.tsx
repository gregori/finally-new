"use client";

import { useEffect, useState } from "react";
import { executeTrade } from "@/lib/api";

interface TradeBarProps {
  selectedTicker: string;
  onTradeComplete: () => void;
}

export function TradeBar({ selectedTicker, onTradeComplete }: TradeBarProps) {
  const [ticker, setTicker] = useState(selectedTicker);
  const [quantity, setQuantity] = useState("");
  const [status, setStatus] = useState<{ message: string; ok: boolean } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setTicker(selectedTicker);
  }, [selectedTicker]);

  async function handleTrade(side: "buy" | "sell") {
    const qty = parseFloat(quantity);
    if (!ticker || isNaN(qty) || qty <= 0) {
      setStatus({ message: "Enter a valid ticker and quantity", ok: false });
      return;
    }

    setLoading(true);
    setStatus(null);
    const res = await executeTrade(ticker.toUpperCase(), qty, side);
    setLoading(false);

    if (res.success) {
      setStatus({ message: `${side.toUpperCase()} ${qty} ${ticker.toUpperCase()} executed`, ok: true });
      setQuantity("");
      onTradeComplete();
    } else {
      setStatus({ message: res.error ?? "Trade failed", ok: false });
    }
  }

  return (
    <div
      className="p-3"
      style={{ borderTop: "1px solid #30363d" }}
    >
      <div
        className="text-xs font-semibold uppercase tracking-wider mb-2"
        style={{ color: "#8b949e" }}
      >
        Trade
      </div>
      <div className="flex gap-2 mb-2">
        <input
          data-testid="trade-ticker-input"
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          placeholder="Ticker"
          className="w-20 text-xs px-2 py-1.5 rounded outline-none"
          style={{
            backgroundColor: "#0d1117",
            color: "#e6edf3",
            border: "1px solid #30363d",
            fontFamily: "monospace",
          }}
        />
        <input
          data-testid="trade-qty-input"
          type="number"
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
          placeholder="Qty"
          min="0"
          className="flex-1 text-xs px-2 py-1.5 rounded outline-none"
          style={{
            backgroundColor: "#0d1117",
            color: "#e6edf3",
            border: "1px solid #30363d",
            fontFamily: "monospace",
          }}
        />
      </div>
      <div className="flex gap-2">
        <button
          data-testid="buy-btn"
          onClick={() => handleTrade("buy")}
          disabled={loading}
          className="flex-1 text-xs font-bold py-1.5 rounded"
          style={{ backgroundColor: "#209dd7", color: "#fff", opacity: loading ? 0.6 : 1 }}
        >
          BUY
        </button>
        <button
          data-testid="sell-btn"
          onClick={() => handleTrade("sell")}
          disabled={loading}
          className="flex-1 text-xs font-bold py-1.5 rounded"
          style={{ backgroundColor: "#f85149", color: "#fff", opacity: loading ? 0.6 : 1 }}
        >
          SELL
        </button>
      </div>
      {status && (
        <div
          data-testid="trade-status"
          className="text-xs mt-2"
          style={{ color: status.ok ? "#3fb950" : "#f85149" }}
        >
          {status.message}
        </div>
      )}
    </div>
  );
}
