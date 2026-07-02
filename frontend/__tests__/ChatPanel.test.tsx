import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChatPanel } from "@/components/ChatPanel";
import * as api from "@/lib/api";

jest.mock("@/lib/api");

const defaultProps = {
  onTradeComplete: jest.fn(),
};

beforeEach(() => {
  jest.clearAllMocks();
});

test("renders empty state initially", () => {
  render(<ChatPanel {...defaultProps} />);
  expect(
    screen.getByText(/Ask FinAlly to analyze/)
  ).toBeInTheDocument();
});

test("shows loading indicator while waiting for response", async () => {
  let resolve: (v: unknown) => void;
  (api.sendChatMessage as jest.Mock).mockImplementation(
    () => new Promise((r) => { resolve = r; })
  );

  render(<ChatPanel {...defaultProps} />);

  const textarea = screen.getByPlaceholderText(/Ask FinAlly/);
  fireEvent.change(textarea, { target: { value: "How is my portfolio?" } });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("FinAlly is thinking...")).toBeInTheDocument();
  });

  // Resolve so the test doesn't hang
  resolve!({ success: true, data: { message: "Looking good!", trades_executed: [], watchlist_changes: [] } });
});

test("renders user and assistant messages", async () => {
  (api.sendChatMessage as jest.Mock).mockResolvedValue({
    success: true,
    data: {
      message: "Your portfolio is well diversified.",
      trades_executed: [],
      watchlist_changes: [],
    },
  });

  render(<ChatPanel {...defaultProps} />);

  const textarea = screen.getByPlaceholderText(/Ask FinAlly/);
  fireEvent.change(textarea, { target: { value: "Analyze my portfolio" } });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("Analyze my portfolio")).toBeInTheDocument();
    expect(
      screen.getByText("Your portfolio is well diversified.")
    ).toBeInTheDocument();
  });
});

test("shows trades executed inline", async () => {
  (api.sendChatMessage as jest.Mock).mockResolvedValue({
    success: true,
    data: {
      message: "I bought 10 shares of AAPL.",
      trades_executed: [{ ticker: "AAPL", side: "buy", quantity: 10 }],
      watchlist_changes: [],
    },
  });

  render(<ChatPanel {...defaultProps} />);

  const textarea = screen.getByPlaceholderText(/Ask FinAlly/);
  fireEvent.change(textarea, { target: { value: "Buy 10 AAPL" } });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(screen.getByText("Trades executed:")).toBeInTheDocument();
    expect(screen.getByText("BUY 10 AAPL")).toBeInTheDocument();
  });
});

test("calls onTradeComplete when trades are executed", async () => {
  const onTradeComplete = jest.fn();
  (api.sendChatMessage as jest.Mock).mockResolvedValue({
    success: true,
    data: {
      message: "Done.",
      trades_executed: [{ ticker: "MSFT", side: "buy", quantity: 5 }],
      watchlist_changes: [],
    },
  });

  render(<ChatPanel onTradeComplete={onTradeComplete} />);

  const textarea = screen.getByPlaceholderText(/Ask FinAlly/);
  fireEvent.change(textarea, { target: { value: "Buy MSFT" } });
  fireEvent.click(screen.getByText("Send"));

  await waitFor(() => {
    expect(onTradeComplete).toHaveBeenCalled();
  });
});
