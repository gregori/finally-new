from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api._response import err, ok
from app.api._trade import (
    InsufficientCashError,
    InsufficientSharesError,
    execute_trade,
)
from app.db import get_db
from app.db.queries import (
    ensure_user_profile,
    get_portfolio_snapshots,
    get_positions,
)

router = APIRouter()


class TradeRequest(BaseModel):
    ticker: str
    side: str
    quantity: float


async def _build_portfolio(db, source) -> dict:
    """Assemble a portfolio summary dict from DB and live prices."""
    profile = await ensure_user_profile(db)
    cash = profile["cash_balance"]
    positions_raw = await get_positions(db)

    positions = []
    total_value = cash

    for pos in positions_raw:
        ticker = pos["ticker"]
        qty = pos["quantity"]
        avg_cost = pos["avg_cost"]
        update = source.get_price(ticker)
        current_price = update.price if update else avg_cost
        unrealized_pnl = (current_price - avg_cost) * qty
        pnl_pct = (current_price / avg_cost - 1) * 100 if avg_cost else 0.0
        total_value += qty * current_price
        positions.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl,
                "pnl_pct": pnl_pct,
            }
        )

    return {"cash": cash, "total_value": total_value, "positions": positions}


@router.get("/portfolio")
async def get_portfolio(request: Request):
    """Return current portfolio: cash, positions, total value, and P&L."""
    source = request.app.state.source
    async with get_db() as db:
        data = await _build_portfolio(db, source)
    return ok(data)


@router.post("/portfolio/trade")
async def trade(body: TradeRequest, request: Request):
    """Execute a market order: buy or sell shares at the current price."""
    ticker = body.ticker.upper().strip()
    side = body.side.lower()
    quantity = body.quantity
    source = request.app.state.source

    if side not in ("buy", "sell"):
        return err("side must be 'buy' or 'sell'", "INVALID_SIDE", 400)
    if quantity <= 0:
        return err("quantity must be positive", "INVALID_QUANTITY", 400)

    if source.get_price(ticker) is None:
        return err(f"No price available for {ticker}", "NO_PRICE", 400)

    async with get_db() as db:
        try:
            result = await execute_trade(ticker, side, quantity, db, source)
        except InsufficientCashError as exc:
            msg = (
                f"Insufficient cash. "
                f"Need ${exc.need:,.2f}, have ${exc.have:,.2f}."
            )
            return err(msg, "INSUFFICIENT_CASH", 400)
        except InsufficientSharesError as exc:
            return err(
                "Insufficient shares. "
                f"Own {exc.owned}, tried to sell {exc.requested}.",
                "INSUFFICIENT_SHARES",
                400,
            )

    return ok(result)


@router.get("/portfolio/history")
async def get_history():
    """Return portfolio value snapshots for the P&L chart."""
    async with get_db() as db:
        snapshots = await get_portfolio_snapshots(db)
    return ok(
        {
            "snapshots": [
                {
                    "total_value": s["total_value"],
                    "recorded_at": s["recorded_at"],
                }
                for s in snapshots
            ]
        }
    )
