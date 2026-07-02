"""Shared trade execution logic used by portfolio and chat routes."""

import aiosqlite

from app.db.queries import (
    ensure_user_profile,
    get_positions,
    record_portfolio_snapshot,
    record_trade,
    remove_position,
    upsert_position,
)
from app.market.interface import MarketDataSource


class InsufficientCashError(Exception):
    """Raised when a buy order exceeds available cash."""

    def __init__(self, need: float, have: float) -> None:
        self.need = need
        self.have = have
        super().__init__(f"Need ${need:,.2f}, have ${have:,.2f}")


class InsufficientSharesError(Exception):
    """Raised when a sell order exceeds owned quantity."""

    def __init__(self, owned: float, requested: float) -> None:
        self.owned = owned
        self.requested = requested
        super().__init__(f"Own {owned}, tried to sell {requested}")


async def execute_trade(
    ticker: str,
    side: str,
    quantity: float,
    db: aiosqlite.Connection,
    source: MarketDataSource,
) -> dict:
    """
    Execute a validated trade and persist all changes.

    Args:
        ticker: Ticker symbol (uppercase).
        side: "buy" or "sell".
        quantity: Number of shares.
        db: Active database connection.
        source: Market data source for current prices.

    Returns:
        Dict with ticker, side, quantity, price, new_cash.

    Raises:
        ValueError: If no price is available for the ticker.
        InsufficientCashError: If a buy exceeds available cash.
        InsufficientSharesError: If a sell exceeds owned quantity.

    """
    price_update = source.get_price(ticker)
    if price_update is None:
        msg = f"No price available for {ticker}"
        raise ValueError(msg)
    price = price_update.price

    profile = await ensure_user_profile(db)
    cash = profile["cash_balance"]

    positions = await get_positions(db)
    pos = next((p for p in positions if p["ticker"] == ticker), None)
    old_qty = pos["quantity"] if pos else 0.0
    old_avg = pos["avg_cost"] if pos else 0.0

    if side == "buy":
        cost = price * quantity
        if cash < cost:
            raise InsufficientCashError(need=cost, have=cash)
        new_qty = old_qty + quantity
        new_avg = (old_qty * old_avg + quantity * price) / new_qty
        new_cash = cash - cost
    else:
        if old_qty < quantity:
            raise InsufficientSharesError(owned=old_qty, requested=quantity)
        new_qty = old_qty - quantity
        new_avg = old_avg
        new_cash = cash + price * quantity

    # Persist changes
    await db.execute(
        "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
        (new_cash, "default"),
    )
    await db.commit()

    if new_qty <= 0:
        await remove_position(db, ticker)
    else:
        await upsert_position(db, ticker, new_qty, new_avg)

    await record_trade(db, ticker, side, quantity, price)

    # Record portfolio snapshot immediately after trade
    all_positions = await get_positions(db)
    total_value = new_cash
    for p in all_positions:
        p_update = source.get_price(p["ticker"])
        if p_update is not None:
            total_value += p["quantity"] * p_update.price
    await record_portfolio_snapshot(db, total_value)

    return {
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "new_cash": new_cash,
    }
