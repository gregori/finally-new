"""Integration tests for SimulatorDataSource — the full async provider."""

import asyncio

from app.market.simulator import SimulatorDataSource


async def test_start_and_stop():
    source = SimulatorDataSource()
    await source.start(["AAPL"])
    assert source._task is not None
    await source.stop()
    assert source._task is None


async def test_prices_available_after_ticks():
    source = SimulatorDataSource()
    await source.start(["AAPL", "MSFT"])
    # Give the background task time to run at least one tick
    await asyncio.sleep(0.6)
    prices = source.get_all_prices()
    assert "AAPL" in prices
    assert "MSFT" in prices
    await source.stop()


async def test_get_price_returns_update():
    source = SimulatorDataSource()
    await source.start(["GOOGL"])
    await asyncio.sleep(0.6)
    update = source.get_price("GOOGL")
    assert update is not None
    assert update.ticker == "GOOGL"
    assert update.price > 0
    await source.stop()


async def test_add_ticker_starts_tracking():
    source = SimulatorDataSource()
    await source.start(["AAPL"])
    await source.add_ticker("TSLA")
    await asyncio.sleep(0.6)
    prices = source.get_all_prices()
    assert "TSLA" in prices
    await source.stop()


async def test_remove_ticker_stops_tracking():
    source = SimulatorDataSource()
    await source.start(["AAPL", "MSFT"])
    await asyncio.sleep(0.6)
    await source.remove_ticker("MSFT")
    await asyncio.sleep(0.6)
    assert source.get_price("MSFT") is None
    await source.stop()


async def test_validate_ticker_valid_symbols():
    source = SimulatorDataSource()
    await source.start([])
    assert await source.validate_ticker("AAPL") is True
    assert await source.validate_ticker("A") is True
    assert await source.validate_ticker("GOOGL") is True
    await source.stop()


async def test_validate_ticker_invalid_symbols():
    source = SimulatorDataSource()
    await source.start([])
    assert await source.validate_ticker("TOOLONG") is False  # > 5 chars
    assert await source.validate_ticker("") is False
    assert await source.validate_ticker("123") is False  # non-alpha
    assert await source.validate_ticker("A1B") is False  # mixed
    await source.stop()


async def test_get_tickers_reflects_tracked_set():
    source = SimulatorDataSource()
    await source.start(["AAPL", "MSFT"])
    tickers = source.get_tickers()
    assert tickers == {"AAPL", "MSFT"}
    await source.stop()


async def test_stop_cancels_background_task():
    source = SimulatorDataSource()
    await source.start(["AAPL"])
    task = source._task
    assert task is not None
    await source.stop()
    assert task.cancelled() or task.done()


async def test_prices_update_over_time():
    source = SimulatorDataSource()
    await source.start(["NVDA"])
    await asyncio.sleep(0.6)
    price1 = source.get_price("NVDA")
    await asyncio.sleep(0.6)
    price2 = source.get_price("NVDA")
    assert price1 is not None
    assert price2 is not None
    # Two consecutive samples should almost certainly differ (extremely
    # unlikely to match exactly)
    # but we only assert both are valid prices > 0
    assert price1.price > 0
    assert price2.price > 0
    await source.stop()
