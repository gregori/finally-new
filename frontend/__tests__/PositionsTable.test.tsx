import React from "react";
import { render, screen } from "@testing-library/react";
import { PositionsTable } from "@/components/PositionsTable";
import type { Position } from "@/lib/api";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 180,
    current_price: 192.5,
    unrealized_pnl: 125,
    pnl_pct: 6.94,
  },
  {
    ticker: "TSLA",
    quantity: 5,
    avg_cost: 250,
    current_price: 230,
    unrealized_pnl: -100,
    pnl_pct: -8.0,
  },
];

test("renders position tickers", () => {
  render(<PositionsTable positions={positions} prices={{}} />);
  expect(screen.getByText("AAPL")).toBeInTheDocument();
  expect(screen.getByText("TSLA")).toBeInTheDocument();
});

test("renders quantities", () => {
  render(<PositionsTable positions={positions} prices={{}} />);
  expect(screen.getByText("10")).toBeInTheDocument();
  expect(screen.getByText("5")).toBeInTheDocument();
});

test("renders profit P&L in green color", () => {
  render(<PositionsTable positions={positions} prices={{}} />);
  // text renders as "+$125.00" (+ prefix, then $, then amount)
  const profitCells = screen.getAllByText(/\+\$125\.00/);
  expect(profitCells.length).toBeGreaterThan(0);
  expect(profitCells[0]).toHaveStyle({ color: "#3fb950" });
});

test("renders loss P&L in red color", () => {
  render(<PositionsTable positions={positions} prices={{}} />);
  // text renders as "$-100.00" ($ then negative amount)
  const lossCells = screen.getAllByText(/\$-100\.00/);
  expect(lossCells.length).toBeGreaterThan(0);
  expect(lossCells[0]).toHaveStyle({ color: "#f85149" });
});

test("shows empty state when no positions", () => {
  render(<PositionsTable positions={[]} prices={{}} />);
  expect(screen.getByText("No open positions")).toBeInTheDocument();
});

test("uses live price from stream when available", () => {
  const prices = {
    AAPL: { price: 200, previous_price: 192.5, change: 7.5, direction: "up" },
  };
  render(<PositionsTable positions={positions} prices={prices} />);
  expect(screen.getByText("$200.00")).toBeInTheDocument();
});
