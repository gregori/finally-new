def build_system_prompt() -> str:
    """Build the system prompt for FinAlly's AI trading assistant."""
    return (
        "You are FinAlly, an expert AI trading assistant embedded"
        " in a simulated trading workstation. Your role: help"
        " users manage their portfolio effectively.\n"
        "\n"
        "Your capabilities:\n"
        "- Analyze portfolio composition, risk concentration, and P&L\n"
        "- Suggest trades with brief, data-driven reasoning\n"
        "- Execute trades when asked or when the user agrees\n"
        "- Add or remove tickers from the watchlist proactively\n"
        "\n"
        "Your style:\n"
        "- Be concise and data-driven. Avoid filler phrases.\n"
        "- Reference actual numbers from the portfolio context.\n"
        "- When recommending trades, briefly state why.\n"
        "\n"
        "Response format — always respond with valid JSON:\n"
        '{"message":"...", "trades":[...], "watchlist_changes":[...]}\n'
        'Trades: {"ticker":str, "side":"buy"|"sell", "quantity":float}\n'
        'Watchlist: {"ticker":str, "action":"add"|"remove"}'
    )


def build_portfolio_context(portfolio: dict) -> str:
    """
    Format portfolio state into a readable context message.

    Args:
        portfolio: Dict with keys: cash, total_value, positions
            (list of position dicts).

    Returns:
        Formatted string describing the current portfolio state.

    """
    cash = portfolio.get("cash", 0.0)
    total_value = portfolio.get("total_value", 0.0)
    positions = portfolio.get("positions", [])

    lines = [
        "=== Current Portfolio State ===",
        f"Cash: ${cash:,.2f}",
        f"Total Value: ${total_value:,.2f}",
    ]

    if positions:
        lines.append(f"Positions ({len(positions)}):")
        for pos in positions:
            ticker = pos.get("ticker", "?")
            qty = pos.get("quantity", 0.0)
            avg_cost = pos.get("avg_cost", 0.0)
            current_price = pos.get("current_price", 0.0)
            unrealized_pnl = pos.get("unrealized_pnl", 0.0)
            pnl_pct = pos.get("pnl_pct", 0.0)
            pnl_sign = "+" if unrealized_pnl >= 0 else "-"
            pct_sign = "+" if pnl_pct >= 0 else "-"
            pnl_str = f"{pnl_sign}${abs(unrealized_pnl):.2f}"
            pct_str = f"({pct_sign}{abs(pnl_pct):.1f}%)"
            lines.append(
                f"  {ticker}: {qty} shares @ avg ${avg_cost:.2f},"
                f" now ${current_price:.2f}, P&L {pnl_str} {pct_str}"
            )
    else:
        lines.append("Positions: none")

    return "\n".join(lines)
