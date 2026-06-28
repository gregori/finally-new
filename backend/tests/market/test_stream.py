"""
Tests for the SSE price stream.

Strategy: test _generate_events directly using a mock request and a patched
asyncio.sleep (for speed). This avoids the fundamental incompatibility between
httpx.ASGITransport and infinite streaming responses — the transport tries to
collect the full response body before returning, which never completes for an
SSE stream.

HTTP-level assertions (status code, content-type, response headers) are
verified by calling the endpoint function directly and inspecting the
StreamingResponse object it returns.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.market.cache import PriceCache
from app.market.interface import MarketDataSource
from app.market.models import PriceUpdate
from app.market.stream import _generate_events, create_stream_router


class StubSource(MarketDataSource):
    """Minimal synchronous-friendly source for stream tests."""

    def __init__(self) -> None:
        self._cache = PriceCache()

    async def start(self, tickers: list[str]) -> None:
        pass

    async def stop(self) -> None:
        pass

    def get_price(self, ticker: str) -> PriceUpdate | None:
        return self._cache.get(ticker)

    def get_all_prices(self) -> dict[str, PriceUpdate]:
        return self._cache.get_all()

    async def add_ticker(self, ticker: str) -> None:
        pass

    async def remove_ticker(self, ticker: str) -> None:
        pass

    async def validate_ticker(self, _ticker: str) -> bool:
        return True

    @property
    def version(self) -> int:
        return self._cache.version

    async def seed(
        self, ticker: str, price: float, prev: float = 0.0
    ) -> None:
        update = PriceUpdate.from_prices(ticker, price, prev or price)
        await self._cache.set(update)


def make_app(source: MarketDataSource) -> FastAPI:
    app = FastAPI()
    app.include_router(create_stream_router(source), prefix="/api")
    return app


def make_mock_request(disconnect_after: int = 1) -> MagicMock:
    """
    Return a mock Request whose is_disconnected() returns False for the first
    `disconnect_after` calls, then True (simulating client disconnect).
    """
    call_count = [0]

    async def is_disconnected() -> bool:
        call_count[0] += 1
        return call_count[0] > disconnect_after

    req = MagicMock()
    req.is_disconnected = is_disconnected
    return req


async def run_generator(
    source: MarketDataSource,
    *,
    disconnect_after: int = 1,
) -> list[dict]:
    """
    Drive _generate_events with a mock request and patched sleep (instant).
    Returns the parsed payloads from all emitted SSE 'data:' lines.
    """
    request = make_mock_request(disconnect_after=disconnect_after)
    with patch("app.market.stream.asyncio.sleep", new_callable=AsyncMock):
        return [
            json.loads(chunk[6:])
            async for chunk in _generate_events(request, source)
            if chunk.startswith("data: ")
        ]


# ---------------------------------------------------------------------------
# Generator-level tests (fast — no real sleep, no HTTP)
# ---------------------------------------------------------------------------


async def test_generator_yields_sse_event_for_seeded_ticker():
    source = StubSource()
    await source.seed("AAPL", 190.0, 189.0)
    events = await run_generator(source)
    assert len(events) == 1
    assert events[0]["ticker"] == "AAPL"
    assert events[0]["price"] == pytest.approx(190.0)


async def test_generator_payload_has_required_fields():
    source = StubSource()
    await source.seed("MSFT", 415.0, 410.0)
    events = await run_generator(source)
    assert len(events) == 1
    assert set(events[0].keys()) == {
        "ticker",
        "price",
        "prev_price",
        "change",
        "change_pct",
        "timestamp",
    }


async def test_generator_emits_event_per_ticker():
    source = StubSource()
    await source.seed("AAPL", 190.0, 189.0)
    await source.seed("TSLA", 250.0, 248.0)
    events = await run_generator(source)
    tickers = {e["ticker"] for e in events}
    assert "AAPL" in tickers
    assert "TSLA" in tickers
    assert len(events) == 2


async def test_generator_emits_nothing_when_cache_empty():
    source = StubSource()
    events = await run_generator(source)
    assert events == []


async def test_generator_stops_on_disconnect():
    source = StubSource()
    await source.seed("AAPL", 190.0, 189.0)
    request = make_mock_request(disconnect_after=0)
    with patch("app.market.stream.asyncio.sleep", new_callable=AsyncMock):
        chunks = [
            c async for c in _generate_events(request, source)
        ]
    assert chunks == []


async def test_generator_skips_push_when_version_unchanged():
    """After emitting a batch, no further events if version doesn't change."""
    source = StubSource()
    await source.seed("JPM", 200.0, 198.0)
    # 3 loop iterations but version stays at 1 — only one batch emitted.
    events = await run_generator(source, disconnect_after=3)
    assert len(events) == 1
    assert events[0]["ticker"] == "JPM"


async def test_generator_emits_on_version_change():
    """A second version bump causes a second batch of events."""
    source = StubSource()
    await source.seed("NVDA", 875.0, 870.0)

    request = make_mock_request(disconnect_after=3)
    payloads: list[dict] = []

    with patch("app.market.stream.asyncio.sleep", new_callable=AsyncMock):
        gen = _generate_events(request, source)
        async for chunk in gen:
            if chunk.startswith("data: "):
                payloads.append(json.loads(chunk[6:]))
            if len(payloads) == 1:
                await source.seed("NVDA", 900.0, 875.0)
                break
        payloads.extend([
            json.loads(chunk[6:])
            async for chunk in gen
            if chunk.startswith("data: ")
        ])

    prices = [e["price"] for e in payloads if e["ticker"] == "NVDA"]
    assert len(prices) >= 2
    assert prices[0] == pytest.approx(875.0)
    assert prices[-1] == pytest.approx(900.0)


async def test_generator_sse_format_is_valid():
    """Each event chunk must follow the SSE 'data: <json>\\n\\n' format."""
    source = StubSource()
    await source.seed("V", 285.0, 284.0)

    request = make_mock_request(disconnect_after=1)
    with patch("app.market.stream.asyncio.sleep", new_callable=AsyncMock):
        raw_chunks = [c async for c in _generate_events(request, source)]

    assert len(raw_chunks) == 1
    chunk = raw_chunks[0]
    assert chunk.startswith("data: ")
    assert chunk.endswith("\n\n")
    json.loads(chunk[6:].strip())  # must be valid JSON


# ---------------------------------------------------------------------------
# Route / integration level
# ---------------------------------------------------------------------------


def test_create_stream_router_registers_price_route():
    source = StubSource()
    router = create_stream_router(source)
    routes = {r.path: r for r in router.routes}
    assert "/stream/prices" in routes


async def test_sse_streaming_response_headers():
    """
    Verify price_stream() returns a StreamingResponse with correct headers.

    httpx.ASGITransport and starlette.testclient both hang on infinite SSE
    streams, so we call the endpoint function directly and inspect the
    StreamingResponse it returns without ever iterating its body.
    """
    source = StubSource()
    await source.seed("AAPL", 190.0, 189.0)
    router = create_stream_router(source)

    route = next(r for r in router.routes if r.path == "/stream/prices")
    endpoint = route.endpoint

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/stream/prices",
        "headers": [],
        "query_string": b"",
    }

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    request = Request(scope, receive)
    response = await endpoint(request)

    assert isinstance(response, StreamingResponse)
    assert response.media_type == "text/event-stream"
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("connection") == "keep-alive"
