"""
Unit tests for MassiveDataSource (Polygon.io REST client).

All HTTP calls are mocked — no real network requests are made.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.market.cache import PriceCache
from app.market.massive_client import (
    FREE_TIER_POLL_INTERVAL_S,
    MassiveDataSource,
)


def make_snap(
    ticker: str,
    last_trade_price: float | None = 150.0,
    day_close: float = 149.0,
    prev_close: float = 148.0,
) -> dict:
    snap: dict = {
        "ticker": ticker,
        "day": {
            "c": day_close,
            "o": 145.0,
            "h": 152.0,
            "l": 144.0,
            "v": 1_000_000,
        },
        "prevDay": {"c": prev_close, "o": 147.0, "h": 150.0, "l": 146.0},
    }
    if last_trade_price is not None:
        snap["lastTrade"] = {"p": last_trade_price, "s": 100, "t": 1718304000}
    return snap


# --- Initialisation ---


def test_default_poll_interval():
    source = MassiveDataSource(api_key="key")
    assert source._poll_interval_s == FREE_TIER_POLL_INTERVAL_S


def test_custom_poll_interval():
    source = MassiveDataSource(api_key="key", poll_interval_s=2.0)
    assert source._poll_interval_s == 2.0


def test_api_key_stored():
    source = MassiveDataSource(api_key="secret")
    assert source._api_key == "secret"


# --- Price extraction ---


def test_extract_prices_uses_last_trade():
    snap = make_snap("AAPL", last_trade_price=190.5, prev_close=189.0)
    price, prev = MassiveDataSource._extract_prices(snap)
    assert price == pytest.approx(190.5)
    assert prev == pytest.approx(189.0)


def test_extract_prices_falls_back_to_day_close():
    snap = make_snap(
        "AAPL", last_trade_price=None, day_close=190.0, prev_close=188.0
    )
    price, prev = MassiveDataSource._extract_prices(snap)
    assert price == pytest.approx(190.0)
    assert prev == pytest.approx(188.0)


def test_extract_prices_empty_last_trade():
    snap = make_snap(
        "MSFT", last_trade_price=None, day_close=415.0, prev_close=410.0
    )
    snap["lastTrade"] = {}
    price, _prev = MassiveDataSource._extract_prices(snap)
    assert price == pytest.approx(415.0)


# --- Snapshot parsing ---


def test_parse_snapshots_returns_updates():
    source = MassiveDataSource(api_key="key")
    snaps = [
        make_snap("AAPL", 190.0, 189.0, 188.0),
        make_snap("MSFT", 415.0, 414.0, 413.0),
    ]
    updates = source._parse_snapshots(snaps)
    assert len(updates) == 2
    tickers = {u.ticker for u in updates}
    assert tickers == {"AAPL", "MSFT"}


def test_parse_snapshots_skips_missing_ticker():
    source = MassiveDataSource(api_key="key")
    snap = make_snap("", 100.0)  # empty ticker
    snap["ticker"] = ""
    updates = source._parse_snapshots([snap])
    assert updates == []


def test_parse_snapshots_skips_malformed_data():
    source = MassiveDataSource(api_key="key")
    bad_snap = {"ticker": "AAPL"}  # missing day/prevDay
    updates = source._parse_snapshots([bad_snap])
    assert updates == []


def test_parse_snapshots_empty_list():
    source = MassiveDataSource(api_key="key")
    assert source._parse_snapshots([]) == []


# --- add/remove ticker ---


async def test_add_ticker_adds_to_set():
    source = MassiveDataSource(api_key="key")
    source._tickers = {"AAPL"}
    await source.add_ticker("MSFT")
    assert "MSFT" in source._tickers


async def test_add_ticker_uppercases():
    source = MassiveDataSource(api_key="key")
    await source.add_ticker("aapl")
    assert "AAPL" in source._tickers


async def test_remove_ticker_removes_from_set():
    source = MassiveDataSource(api_key="key")
    source._tickers = {"AAPL", "MSFT"}
    source._cache = PriceCache()
    await source.remove_ticker("MSFT")
    assert "MSFT" not in source._tickers


# --- poll_once error handling ---


async def test_poll_once_429_logs_warning(caplog):
    source = MassiveDataSource(api_key="key", poll_interval_s=0.01)
    source._tickers = {"AAPL"}
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Too Many Requests", request=MagicMock(), response=mock_resp
    )
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client

    with caplog.at_level(logging.WARNING, logger="app.market.massive_client"):
        await source._poll_once()
    assert any("rate limit" in r.message.lower() for r in caplog.records)


async def test_poll_once_403_logs_error(caplog):
    source = MassiveDataSource(api_key="bad_key", poll_interval_s=0.01)
    source._tickers = {"AAPL"}
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Forbidden", request=MagicMock(), response=mock_resp
    )
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client

    with caplog.at_level(logging.ERROR, logger="app.market.massive_client"):
        await source._poll_once()
    assert any("MASSIVE_API_KEY" in r.message for r in caplog.records)


async def test_poll_once_timeout_logs_warning(caplog):
    source = MassiveDataSource(api_key="key", poll_interval_s=0.01)
    source._tickers = {"AAPL"}
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("timed out")
    source._client = mock_client

    with caplog.at_level(logging.WARNING, logger="app.market.massive_client"):
        await source._poll_once()
    assert any("timed out" in r.message.lower() for r in caplog.records)


async def test_poll_once_happy_path_updates_cache():
    source = MassiveDataSource(api_key="key", poll_interval_s=0.01)
    source._tickers = {"AAPL"}
    source._cache = PriceCache()

    payload = {"tickers": [make_snap("AAPL", 190.0, 189.0, 188.0)]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = payload
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client

    await source._poll_once()
    update = source.get_price("AAPL")
    assert update is not None
    assert update.price == pytest.approx(190.0)


# --- validate_ticker ---


async def test_validate_ticker_too_long_returns_false():
    source = MassiveDataSource(api_key="key")
    source._client = AsyncMock()
    assert await source.validate_ticker("TOOLONG") is False


async def test_validate_ticker_empty_returns_false():
    source = MassiveDataSource(api_key="key")
    source._client = AsyncMock()
    assert await source.validate_ticker("") is False


async def test_validate_ticker_no_client_returns_false():
    source = MassiveDataSource(api_key="key")
    source._client = None
    assert await source.validate_ticker("AAPL") is False


async def test_validate_ticker_ok_response_returns_true():
    source = MassiveDataSource(api_key="key")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": "OK", "results": {}}
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client
    assert await source.validate_ticker("AAPL") is True


async def test_validate_ticker_404_returns_false():
    source = MassiveDataSource(api_key="key")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client
    assert await source.validate_ticker("ZZZZZ") is False


async def test_validate_ticker_before_start_logs_warning(caplog):
    source = MassiveDataSource(api_key="key")
    # _client is None by default (start() not called)
    with caplog.at_level(logging.WARNING, logger="app.market.massive_client"):
        result = await source.validate_ticker("AAPL")
    assert result is False
    assert any("before start" in r.message for r in caplog.records)


# --- start / stop lifecycle ---


async def test_start_creates_client_and_task():
    source = MassiveDataSource(api_key="key", poll_interval_s=60.0)
    await source.start(["AAPL"])
    assert source._client is not None
    assert source._task is not None
    await source.stop()


async def test_stop_closes_client_and_clears_task():
    source = MassiveDataSource(api_key="key", poll_interval_s=60.0)
    await source.start(["AAPL"])
    await source.stop()
    assert source._client is None
    assert source._task is None


async def test_stop_is_idempotent():
    source = MassiveDataSource(api_key="key", poll_interval_s=60.0)
    await source.start(["AAPL"])
    await source.stop()
    await source.stop()  # second stop must not raise


async def test_start_populates_ticker_set():
    source = MassiveDataSource(api_key="key", poll_interval_s=60.0)
    await source.start(["aapl", "MSFT"])
    assert source.get_tickers() == {"AAPL", "MSFT"}
    await source.stop()


# --- version property ---


async def test_version_starts_at_zero():
    source = MassiveDataSource(api_key="key")
    assert source.version == 0


async def test_version_increments_after_successful_poll():
    source = MassiveDataSource(api_key="key", poll_interval_s=0.01)
    source._tickers = {"AAPL"}
    source._cache = PriceCache()

    payload = {"tickers": [make_snap("AAPL", 190.0, 189.0, 188.0)]}
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = payload
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp
    source._client = mock_client

    version_before = source.version
    await source._poll_once()
    assert source.version > version_before
