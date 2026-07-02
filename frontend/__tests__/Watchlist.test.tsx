import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Watchlist } from "@/components/Watchlist";
import * as api from "@/lib/api";

jest.mock("@/lib/api");

const mockPrices = {
  AAPL: { price: 192.5, previous_price: 191.0, change: 1.5, direction: "up" },
  GOOGL: { price: 175.0, previous_price: 176.0, change: -1.0, direction: "down" },
};

const mockSparklines = {
  AAPL: [190, 191, 192, 192.5],
  GOOGL: [176, 175.5, 175],
};

const defaultProps = {
  tickers: ["AAPL", "GOOGL"],
  prices: mockPrices,
  sparklines: mockSparklines,
  selectedTicker: "AAPL",
  onSelect: jest.fn(),
  onWatchlistChange: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders all tickers", () => {
  render(<Watchlist {...defaultProps} />);
  expect(screen.getByText("AAPL")).toBeInTheDocument();
  expect(screen.getByText("GOOGL")).toBeInTheDocument();
});

test("renders prices for tickers", () => {
  render(<Watchlist {...defaultProps} />);
  expect(screen.getByText("$192.50")).toBeInTheDocument();
  expect(screen.getByText("$175.00")).toBeInTheDocument();
});

test("calls onSelect when ticker row is clicked", () => {
  const onSelect = jest.fn();
  render(<Watchlist {...defaultProps} onSelect={onSelect} />);
  fireEvent.click(screen.getByText("GOOGL"));
  expect(onSelect).toHaveBeenCalledWith("GOOGL");
});

test("calls removeFromWatchlist and onWatchlistChange on remove", async () => {
  (api.removeFromWatchlist as jest.Mock).mockResolvedValue({ success: true });
  const onWatchlistChange = jest.fn();
  render(<Watchlist {...defaultProps} onWatchlistChange={onWatchlistChange} />);

  const removeButtons = screen.getAllByTitle("Remove");
  fireEvent.click(removeButtons[0]);

  await waitFor(() => {
    expect(api.removeFromWatchlist).toHaveBeenCalledWith("AAPL");
    expect(onWatchlistChange).toHaveBeenCalled();
  });
});

test("adds ticker on add button click", async () => {
  (api.addToWatchlist as jest.Mock).mockResolvedValue({ success: true });
  const onWatchlistChange = jest.fn();
  render(<Watchlist {...defaultProps} onWatchlistChange={onWatchlistChange} />);

  const input = screen.getByPlaceholderText("Add ticker...");
  fireEvent.change(input, { target: { value: "TSLA" } });
  fireEvent.click(screen.getByText("+"));

  await waitFor(() => {
    expect(api.addToWatchlist).toHaveBeenCalledWith("TSLA");
    expect(onWatchlistChange).toHaveBeenCalled();
  });
});

test("shows error when add fails", async () => {
  (api.addToWatchlist as jest.Mock).mockResolvedValue({
    success: false,
    error: "Unknown ticker",
  });
  render(<Watchlist {...defaultProps} />);

  const input = screen.getByPlaceholderText("Add ticker...");
  fireEvent.change(input, { target: { value: "FAKE" } });
  fireEvent.click(screen.getByText("+"));

  await waitFor(() => {
    expect(screen.getByText("Unknown ticker")).toBeInTheDocument();
  });
});
