from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api._response import err, ok
from app.db import get_db
from app.db.queries import (
    add_to_watchlist,
    get_watchlist,
    remove_from_watchlist,
)

router = APIRouter()


class AddTickerRequest(BaseModel):
    ticker: str


def _enrich(tickers: list[str], source) -> list[dict]:
    """Combine ticker list with current price data from the market source."""
    result = []
    for ticker in tickers:
        update = source.get_price(ticker)
        if update is not None:
            result.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "previous_price": update.prev_price,
                    "change": update.change,
                    "direction": (
                        "up" if update.price >= update.prev_price else "down"
                    ),
                }
            )
        else:
            result.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "change": None,
                    "direction": None,
                }
            )
    return result


@router.get("/watchlist")
async def get_watchlist_route(request: Request):
    """Return watchlist tickers enriched with current prices."""
    source = request.app.state.source
    async with get_db() as db:
        tickers = await get_watchlist(db)
    return ok({"watchlist": _enrich(tickers, source)})


@router.post("/watchlist")
async def add_ticker(body: AddTickerRequest, request: Request):
    """Add a ticker to the watchlist after validation."""
    ticker = body.ticker.upper().strip()
    source = request.app.state.source

    if not await source.validate_ticker(ticker):
        return err(f"Unknown ticker: {ticker}", "UNKNOWN_TICKER", 400)

    async with get_db() as db:
        existing = await get_watchlist(db)
        if ticker in existing:
            return err(
                f"{ticker} is already in your watchlist",
                "DUPLICATE_TICKER",
                409,
            )
        await add_to_watchlist(db, ticker)

    await source.add_ticker(ticker)

    async with get_db() as db:
        tickers = await get_watchlist(db)
    return ok({"watchlist": _enrich(tickers, source)})


@router.delete("/watchlist/{ticker}")
async def remove_ticker(ticker: str, request: Request):
    """Remove a ticker from the watchlist."""
    ticker = ticker.upper()
    source = request.app.state.source

    async with get_db() as db:
        await remove_from_watchlist(db, ticker)

    await source.remove_ticker(ticker)
    return ok({})
