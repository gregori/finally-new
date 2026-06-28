"""Unit tests for PriceCache."""

import asyncio

import pytest

from app.market.cache import PriceCache
from app.market.models import PriceUpdate


def make_update(
    ticker: str, price: float = 100.0, prev: float = 99.0
) -> PriceUpdate:
    return PriceUpdate.from_prices(ticker, price, prev)


def test_empty_cache_get_returns_none():
    cache = PriceCache()
    assert cache.get("AAPL") is None


def test_empty_cache_get_price_returns_none():
    cache = PriceCache()
    assert cache.get_price("AAPL") is None


def test_empty_cache_get_all_returns_empty_dict():
    cache = PriceCache()
    assert cache.get_all() == {}


async def test_set_and_get():
    cache = PriceCache()
    update = make_update("AAPL", 190.0)
    await cache.set(update)
    result = cache.get("AAPL")
    assert result is update


async def test_get_price_returns_price():
    cache = PriceCache()
    await cache.set(make_update("MSFT", 415.0))
    assert cache.get_price("MSFT") == pytest.approx(415.0)


async def test_set_many_sets_all():
    cache = PriceCache()
    updates = [make_update("AAPL", 190.0), make_update("GOOGL", 175.0)]
    await cache.set_many(updates)
    assert cache.get("AAPL") is not None
    assert cache.get("GOOGL") is not None


async def test_get_all_returns_snapshot_copy():
    cache = PriceCache()
    await cache.set(make_update("AAPL", 190.0))
    snapshot = cache.get_all()
    # Modifying the snapshot must not affect the cache
    snapshot["AAPL"] = None  # type: ignore[assignment]
    assert cache.get("AAPL") is not None


async def test_version_starts_at_zero():
    cache = PriceCache()
    assert cache.version == 0


async def test_version_increments_on_set():
    cache = PriceCache()
    await cache.set(make_update("AAPL"))
    assert cache.version == 1
    await cache.set(make_update("AAPL"))
    assert cache.version == 2


async def test_version_increments_once_on_set_many():
    cache = PriceCache()
    await cache.set_many([make_update("AAPL"), make_update("MSFT")])
    assert cache.version == 1


async def test_set_many_empty_list_does_not_increment_version():
    cache = PriceCache()
    await cache.set_many([])
    assert cache.version == 0


async def test_remove_existing_ticker():
    cache = PriceCache()
    await cache.set(make_update("AAPL"))
    await cache.remove("AAPL")
    assert cache.get("AAPL") is None


async def test_remove_nonexistent_ticker_does_not_raise():
    cache = PriceCache()
    await cache.remove("NONEXISTENT")  # should not raise


async def test_overwrite_updates_price():
    cache = PriceCache()
    await cache.set(make_update("AAPL", 190.0))
    await cache.set(make_update("AAPL", 195.0))
    assert cache.get_price("AAPL") == pytest.approx(195.0)


async def test_concurrent_writers_do_not_corrupt_cache():
    """Multiple concurrent set_many calls must all land without data loss."""
    cache = PriceCache()
    tickers_a = ["AAPL", "MSFT", "GOOGL"]
    tickers_b = ["TSLA", "NVDA", "META"]

    async def write_batch(tickers: list[str], price: float) -> None:
        for _ in range(20):
            updates = [make_update(t, price) for t in tickers]
            await cache.set_many(updates)

    await asyncio.gather(
        write_batch(tickers_a, 100.0), write_batch(tickers_b, 200.0)
    )

    for t in tickers_a:
        assert cache.get(t) is not None
    for t in tickers_b:
        assert cache.get(t) is not None
    assert cache.version > 0


async def test_remove_increments_version():
    cache = PriceCache()
    await cache.set(make_update("AAPL"))
    version_before = cache.version
    await cache.remove("AAPL")
    assert cache.version > version_before
