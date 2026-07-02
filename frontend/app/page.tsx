"use client";

import { useCallback, useEffect, useState } from "react";
import { getPortfolio, getPortfolioHistory, getWatchlist } from "@/lib/api";
import type { Portfolio, PortfolioSnapshot } from "@/lib/api";
import { usePriceStream } from "@/hooks/usePriceStream";
import { Header } from "@/components/Header";
import { Watchlist } from "@/components/Watchlist";
import { MainChart } from "@/components/MainChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";
import { PnLChart } from "@/components/PnLChart";

export default function Home() {
  const [selectedTicker, setSelectedTicker] = useState("AAPL");
  const [watchlistTickers, setWatchlistTickers] = useState<string[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio>({
    cash: 10000,
    total_value: 10000,
    positions: [],
  });
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);

  const { prices, sparklines, connectionStatus } = usePriceStream();

  const refreshWatchlist = useCallback(async () => {
    const res = await getWatchlist();
    if (res.success && res.data) {
      setWatchlistTickers(res.data.watchlist.map((w) => w.ticker));
    }
  }, []);

  const refreshPortfolio = useCallback(async () => {
    const [portRes, histRes] = await Promise.all([
      getPortfolio(),
      getPortfolioHistory(),
    ]);
    if (portRes.success && portRes.data) {
      setPortfolio(portRes.data);
    }
    if (histRes.success && histRes.data) {
      setSnapshots(histRes.data.snapshots);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshWatchlist();
    refreshPortfolio();
  }, [refreshWatchlist, refreshPortfolio]);

  // Refresh portfolio every 5 seconds
  useEffect(() => {
    const interval = setInterval(refreshPortfolio, 5000);
    return () => clearInterval(interval);
  }, [refreshPortfolio]);

  // Refresh history every 30 seconds
  useEffect(() => {
    const interval = setInterval(async () => {
      const res = await getPortfolioHistory();
      if (res.success && res.data) {
        setSnapshots(res.data.snapshots);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleTradeComplete = useCallback(() => {
    refreshPortfolio();
    refreshWatchlist();
  }, [refreshPortfolio, refreshWatchlist]);

  // Live total value from stream
  const liveTotal = portfolio.positions.reduce((sum, p) => {
    const livePrice = prices[p.ticker]?.price ?? p.current_price;
    return sum + livePrice * p.quantity;
  }, portfolio.cash);

  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ backgroundColor: "#0d1117", color: "#e6edf3" }}
    >
      <Header
        totalValue={liveTotal}
        cash={portfolio.cash}
        connectionStatus={connectionStatus}
      />

      {/* Main grid layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Watchlist */}
        <div
          className="w-52 flex-shrink-0 overflow-hidden"
          style={{ backgroundColor: "#161b22" }}
        >
          <Watchlist
            tickers={watchlistTickers}
            prices={prices}
            sparklines={sparklines}
            selectedTicker={selectedTicker}
            onSelect={setSelectedTicker}
            onWatchlistChange={refreshWatchlist}
          />
        </div>

        {/* Center: Charts + Positions */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Top: Main chart */}
          <div
            className="flex-1 overflow-hidden"
            style={{ borderBottom: "1px solid #30363d", minHeight: 0 }}
          >
            <MainChart
              ticker={selectedTicker}
              sparklineData={sparklines[selectedTicker] ?? []}
            />
          </div>

          {/* Bottom: Heatmap + Positions + PnL */}
          <div className="flex h-56 overflow-hidden">
            {/* Heatmap */}
            <div
              className="w-64 flex-shrink-0 overflow-hidden"
              style={{
                backgroundColor: "#161b22",
                borderRight: "1px solid #30363d",
              }}
            >
              <PortfolioHeatmap
                positions={portfolio.positions}
                totalValue={liveTotal}
              />
            </div>

            {/* Positions table */}
            <div
              className="flex-1 overflow-hidden"
              style={{
                backgroundColor: "#161b22",
                borderRight: "1px solid #30363d",
              }}
            >
              <PositionsTable positions={portfolio.positions} prices={prices} />
            </div>

            {/* PnL Chart */}
            <div
              className="w-64 flex-shrink-0 overflow-hidden"
              style={{ backgroundColor: "#161b22" }}
            >
              <PnLChart snapshots={snapshots} />
            </div>
          </div>
        </div>

        {/* Right: Chat + Trade */}
        <div
          className="w-72 flex-shrink-0 flex flex-col overflow-hidden"
          style={{
            backgroundColor: "#161b22",
            borderLeft: "1px solid #30363d",
          }}
        >
          <div className="flex-1 overflow-hidden">
            <ChatPanel onTradeComplete={handleTradeComplete} />
          </div>
          <TradeBar
            selectedTicker={selectedTicker}
            onTradeComplete={handleTradeComplete}
          />
        </div>
      </div>
    </div>
  );
}
