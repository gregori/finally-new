import asyncio
import contextlib
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import app.config  # validates OPENCODE_API_KEY at import time
from app.api import chat, portfolio, system, watchlist
from app.db import get_db, init_db
from app.db.queries import (
    ensure_user_profile,
    get_positions,
    record_portfolio_snapshot,
)
from app.market import create_market_data_source
from app.market.seed_prices import SEED_PRICES

logger = logging.getLogger(__name__)


async def _snapshot_loop(source) -> None:
    """Record portfolio value snapshots every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            async with get_db() as db:
                profile = await ensure_user_profile(db)
                cash = profile["cash_balance"]
                positions = await get_positions(db)
                total_value = cash
                for pos in positions:
                    update = source.get_price(pos["ticker"])
                    if update is not None:
                        total_value += pos["quantity"] * update.price
                await record_portfolio_snapshot(db, total_value)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start market data and background tasks; shut down cleanly on exit."""
    await init_db()

    source = create_market_data_source()
    await source.start(list(SEED_PRICES.keys()))

    # Give simulator one tick cycle to populate the price cache before serving
    await asyncio.sleep(0.1)

    app.state.source = source
    snapshot_task = asyncio.create_task(_snapshot_loop(source))

    yield

    snapshot_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await snapshot_task
    await source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

app.include_router(system.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/api/stream/prices")
async def price_stream(request: Request) -> StreamingResponse:
    """SSE stream of live price updates for all watched tickers."""
    source = request.app.state.source
    return StreamingResponse(
        _generate_price_events(request, source),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_price_events(request: Request, source):
    """Yield SSE frames for every price change detected."""
    last_version = -1
    while True:
        if await request.is_disconnected():
            break
        current_version = source.version
        if current_version != last_version:
            prices = source.get_all_prices()
            for update in prices.values():
                payload = {
                    "ticker": update.ticker,
                    "price": update.price,
                    "prev_price": update.prev_price,
                    "change": update.change,
                    "change_pct": update.change_pct,
                    "timestamp": update.timestamp,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            last_version = current_version
        await asyncio.sleep(0.5)


# Mount static frontend if the build output exists
_static_dir = os.getenv("STATIC_DIR", "/app/static")
if Path(_static_dir).exists():
    app.mount(
        "/",
        StaticFiles(directory=_static_dir, html=True),
        name="static",
    )
