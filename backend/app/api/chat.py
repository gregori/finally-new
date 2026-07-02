from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api._response import err, ok
from app.api._trade import execute_trade
from app.db import get_db
from app.db.queries import (
    add_to_watchlist,
    ensure_user_profile,
    get_chat_messages,
    get_positions,
    get_watchlist,
    remove_from_watchlist,
    save_chat_message,
)
from app.llm import LLMResponse
from app.llm import chat as llm_chat

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


async def _build_portfolio(db, source) -> dict:
    """Assemble portfolio context dict for the LLM."""
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


async def _validate_trades(db, source, trade_actions) -> list[str]:
    """Return a list of validation error strings; empty means all are valid."""
    errors: list[str] = []
    for action in trade_actions:
        ticker = action.ticker.upper()
        update = source.get_price(ticker)
        if update is None:
            errors.append(f"No price available for {ticker}")
            continue
        if action.side == "buy":
            profile = await ensure_user_profile(db)
            cost = update.price * action.quantity
            if profile["cash_balance"] < cost:
                have = profile["cash_balance"]
                errors.append(
                    f"Insufficient cash to buy {action.quantity} {ticker} "
                    f"(need ${cost:,.2f}, have ${have:,.2f})"
                )
        else:
            positions = await get_positions(db)
            pos = next((p for p in positions if p["ticker"] == ticker), None)
            owned = pos["quantity"] if pos else 0.0
            if owned < action.quantity:
                errors.append(
                    f"Insufficient shares to sell {action.quantity} {ticker}"
                    f" (own {owned})"
                )
    return errors


async def _apply_trades(db, source, trade_actions) -> list[dict]:
    """Execute all trade actions and return result dicts."""
    results = []
    for action in trade_actions:
        ticker = action.ticker.upper()
        result = await execute_trade(
            ticker, action.side, action.quantity, db, source
        )
        results.append(result)
    return results


async def _apply_watchlist_changes(db, source, changes) -> list[dict]:
    """Apply watchlist add/remove changes and return applied list."""
    applied = []
    existing = await get_watchlist(db)
    for change in changes:
        ticker = change.ticker.upper()
        if change.action == "add":
            if await source.validate_ticker(ticker):
                await add_to_watchlist(db, ticker)
                await source.add_ticker(ticker)
                applied.append({"ticker": ticker, "action": "add"})
        elif change.action == "remove" and ticker in existing:
            await remove_from_watchlist(db, ticker)
            await source.remove_ticker(ticker)
            applied.append({"ticker": ticker, "action": "remove"})
    return applied


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """Send a message to the AI assistant and execute any returned actions."""
    source = request.app.state.source
    user_message = body.message.strip()

    if not user_message:
        return err("Message cannot be empty.", "EMPTY_MESSAGE", 400)

    async with get_db() as db:
        portfolio = await _build_portfolio(db, source)
        history_rows = await get_chat_messages(db, limit=20)

    history = [
        {"role": r["role"], "content": r["content"]} for r in history_rows
    ]

    try:
        llm_response: LLMResponse = await llm_chat(
            user_message, history, portfolio
        )
    except ValueError as exc:
        return err(str(exc), "LLM_ERROR", 503)

    response_message = llm_response.message
    trades_executed: list[dict] = []
    watchlist_changes_applied: list[dict] = []

    if llm_response.trades:
        async with get_db() as db:
            errors = await _validate_trades(db, source, llm_response.trades)
            if errors:
                summary = "; ".join(errors)
                response_message = (
                    f"{response_message}\n\n"
                    "Trade validation failed — no trades were executed: "
                    f"{summary}."
                )
            else:
                trades_executed = await _apply_trades(
                    db, source, llm_response.trades
                )

    if llm_response.watchlist_changes:
        async with get_db() as db:
            watchlist_changes_applied = await _apply_watchlist_changes(
                db, source, llm_response.watchlist_changes
            )

    actions_payload = {
        "trades": trades_executed,
        "watchlist_changes": watchlist_changes_applied,
    }
    async with get_db() as db:
        await save_chat_message(db, "user", user_message)
        await save_chat_message(
            db, "assistant", response_message, actions=actions_payload
        )

    return ok(
        {
            "message": response_message,
            "trades_executed": trades_executed,
            "watchlist_changes": watchlist_changes_applied,
        }
    )
