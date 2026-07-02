"use client";

import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  trades?: { ticker: string; side: string; quantity: number }[];
  watchlist_changes?: { ticker: string; action: string }[];
}

interface ChatPanelProps {
  onTradeComplete: () => void;
}

export function ChatPanel({ onTradeComplete }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);

    const res = await sendChatMessage(text);
    setLoading(false);

    if (res.success && res.data) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.data!.message,
          trades: res.data!.trades_executed,
          watchlist_changes: res.data!.watchlist_changes,
        },
      ]);
      if (res.data.trades_executed?.length > 0) {
        onTradeComplete();
      }
    } else {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.error ?? "Something went wrong. Please try again.",
        },
      ]);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div
        className="px-3 py-2 text-xs font-semibold uppercase tracking-wider"
        style={{ borderBottom: "1px solid #30363d", color: "#8b949e" }}
      >
        AI Assistant
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && (
          <div
            className="text-xs text-center mt-4"
            style={{ color: "#484f58" }}
          >
            Ask FinAlly to analyze your portfolio, suggest trades, or manage your watchlist.
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            data-testid="chat-message"
            data-role={msg.role}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className="max-w-[90%] text-xs rounded px-3 py-2 space-y-2"
              style={{
                backgroundColor:
                  msg.role === "user" ? "#1f3a4f" : "#1a1f2e",
                color: "#e6edf3",
                border: "1px solid #30363d",
              }}
            >
              <p style={{ lineHeight: "1.5" }}>{msg.content}</p>

              {msg.trades && msg.trades.length > 0 && (
                <div
                  className="rounded px-2 py-1 text-xs"
                  style={{
                    backgroundColor: "#0d1117",
                    borderLeft: "2px solid #3fb950",
                  }}
                >
                  <div className="font-semibold mb-1" style={{ color: "#3fb950" }}>
                    Trades executed:
                  </div>
                  {msg.trades.map((t, j) => (
                    <div key={j} style={{ color: "#8b949e" }}>
                      {t.side.toUpperCase()} {t.quantity} {t.ticker}
                    </div>
                  ))}
                </div>
              )}

              {msg.watchlist_changes && msg.watchlist_changes.length > 0 && (
                <div
                  className="rounded px-2 py-1 text-xs"
                  style={{
                    backgroundColor: "#0d1117",
                    borderLeft: "2px solid #209dd7",
                  }}
                >
                  <div className="font-semibold mb-1" style={{ color: "#209dd7" }}>
                    Watchlist changes:
                  </div>
                  {msg.watchlist_changes.map((w, j) => (
                    <div key={j} style={{ color: "#8b949e" }}>
                      {w.action === "add" ? "Added" : "Removed"} {w.ticker}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div data-testid="chat-loading" className="flex justify-start">
            <div
              className="text-xs rounded px-3 py-2"
              style={{
                backgroundColor: "#1a1f2e",
                color: "#8b949e",
                border: "1px solid #30363d",
              }}
            >
              FinAlly is thinking...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="p-3" style={{ borderTop: "1px solid #30363d" }}>
        <div className="flex gap-2">
          <textarea
            data-testid="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask FinAlly anything... (Enter to send)"
            rows={2}
            className="flex-1 text-xs px-2 py-1.5 rounded outline-none resize-none"
            style={{
              backgroundColor: "#0d1117",
              color: "#e6edf3",
              border: "1px solid #30363d",
              fontFamily: "sans-serif",
            }}
          />
          <button
            data-testid="chat-send-btn"
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="text-xs font-bold px-3 py-1.5 rounded self-end"
            style={{
              backgroundColor: "#753991",
              color: "#fff",
              opacity: loading || !input.trim() ? 0.6 : 1,
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
