"use client";

interface HeaderProps {
  totalValue: number;
  cash: number;
  connectionStatus: "connected" | "reconnecting" | "disconnected";
}

const STATUS_COLORS = {
  connected: "#3fb950",
  reconnecting: "#ecad0a",
  disconnected: "#f85149",
};

export function Header({ totalValue, cash, connectionStatus }: HeaderProps) {
  const statusColor = STATUS_COLORS[connectionStatus];

  return (
    <header
      className="flex items-center justify-between px-4 py-2 border-b"
      style={{ borderColor: "#30363d", backgroundColor: "#161b22" }}
    >
      <div className="flex items-center gap-3">
        <span
          className="text-lg font-bold tracking-wider"
          style={{ color: "#ecad0a", fontFamily: "monospace" }}
        >
          FinAlly
        </span>
        <span className="text-xs" style={{ color: "#484f58" }}>
          AI Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="text-xs" style={{ color: "#8b949e" }}>
            Portfolio
          </div>
          <div
            data-testid="portfolio-value"
            className="text-sm font-mono font-semibold"
            style={{ color: "#e6edf3" }}
          >
            ${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="text-right">
          <div className="text-xs" style={{ color: "#8b949e" }}>
            Cash
          </div>
          <div
            data-testid="cash-balance"
            className="text-sm font-mono"
            style={{ color: "#e6edf3" }}
          >
            ${cash.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div
            data-testid="connection-status"
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: statusColor }}
            title={connectionStatus}
          />
          <span className="text-xs" style={{ color: "#8b949e" }}>
            {connectionStatus}
          </span>
        </div>
      </div>
    </header>
  );
}
