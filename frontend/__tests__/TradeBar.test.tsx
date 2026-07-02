import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { TradeBar } from "@/components/TradeBar";
import * as api from "@/lib/api";

jest.mock("@/lib/api");

const defaultProps = {
  selectedTicker: "AAPL",
  onTradeComplete: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders with selected ticker pre-filled", () => {
  render(<TradeBar {...defaultProps} />);
  const tickerInput = screen.getByPlaceholderText("Ticker") as HTMLInputElement;
  expect(tickerInput.value).toBe("AAPL");
});

test("calls executeTrade with correct args on BUY", async () => {
  (api.executeTrade as jest.Mock).mockResolvedValue({ success: true });
  render(<TradeBar {...defaultProps} />);

  fireEvent.change(screen.getByPlaceholderText("Qty"), {
    target: { value: "5" },
  });
  fireEvent.click(screen.getByText("BUY"));

  await waitFor(() => {
    expect(api.executeTrade).toHaveBeenCalledWith("AAPL", 5, "buy");
  });
});

test("calls executeTrade with correct args on SELL", async () => {
  (api.executeTrade as jest.Mock).mockResolvedValue({ success: true });
  render(<TradeBar {...defaultProps} />);

  fireEvent.change(screen.getByPlaceholderText("Qty"), {
    target: { value: "3" },
  });
  fireEvent.click(screen.getByText("SELL"));

  await waitFor(() => {
    expect(api.executeTrade).toHaveBeenCalledWith("AAPL", 3, "sell");
  });
});

test("calls onTradeComplete after successful trade", async () => {
  const onTradeComplete = jest.fn();
  (api.executeTrade as jest.Mock).mockResolvedValue({ success: true });
  render(<TradeBar {...defaultProps} onTradeComplete={onTradeComplete} />);

  fireEvent.change(screen.getByPlaceholderText("Qty"), {
    target: { value: "1" },
  });
  fireEvent.click(screen.getByText("BUY"));

  await waitFor(() => {
    expect(onTradeComplete).toHaveBeenCalled();
  });
});

test("shows error message on trade failure", async () => {
  (api.executeTrade as jest.Mock).mockResolvedValue({
    success: false,
    error: "Insufficient funds",
  });
  render(<TradeBar {...defaultProps} />);

  fireEvent.change(screen.getByPlaceholderText("Qty"), {
    target: { value: "100" },
  });
  fireEvent.click(screen.getByText("BUY"));

  await waitFor(() => {
    expect(screen.getByText("Insufficient funds")).toBeInTheDocument();
  });
});

test("shows validation message when no quantity", async () => {
  render(<TradeBar {...defaultProps} />);
  fireEvent.click(screen.getByText("BUY"));

  await waitFor(() => {
    expect(
      screen.getByText("Enter a valid ticker and quantity")
    ).toBeInTheDocument();
  });
});
