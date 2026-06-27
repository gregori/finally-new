import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .interface import MarketDataSource

logger = logging.getLogger(__name__)

SSE_PUSH_INTERVAL_S = 0.5


def create_stream_router(source: MarketDataSource) -> APIRouter:
    """Create a FastAPI router with the /stream/prices SSE endpoint.

    The router captures the market data source at creation time.
    Mount this router under /api in the FastAPI app.
    """
    router = APIRouter()

    @router.get("/stream/prices")
    async def price_stream(request: Request) -> StreamingResponse:
        return StreamingResponse(
            _generate_events(request, source),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router


async def _generate_events(
    request: Request, source: MarketDataSource
) -> AsyncGenerator[str, None]:
    """Yield SSE data frames for every price in the cache every 500ms.

    Uses version-based change detection: only emits events when the
    underlying cache has been updated since the last push cycle.
    """
    last_version = -1
    cache = getattr(source, "_cache", None)

    while True:
        if await request.is_disconnected():
            break

        current_version = cache.version if cache is not None else 0
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

        await asyncio.sleep(SSE_PUSH_INTERVAL_S)
