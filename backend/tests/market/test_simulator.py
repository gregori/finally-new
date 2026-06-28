"""Unit tests for GBMSimulator — price engine internals."""

import math

import pytest

from app.market.seed_prices import DEFAULT_PARAMS, SEED_PRICES, TICKER_PARAMS
from app.market.simulator import (
    DT,
    EVENT_PROBABILITY,
    KNOWN_TICKERS,
    TICK_INTERVAL_S,
    TRADING_DAYS_PER_YEAR,
    TRADING_HOURS_PER_DAY,
    GBMSimulator,
)


def test_tick_interval_constant():
    assert TICK_INTERVAL_S == 0.5


def test_dt_formula():
    expected = TICK_INTERVAL_S / (
        TRADING_DAYS_PER_YEAR * TRADING_HOURS_PER_DAY * 3600
    )
    assert pytest.approx(expected) == DT


def test_event_probability_positive():
    assert EVENT_PROBABILITY > 0
    assert EVENT_PROBABILITY < 1


def test_seed_prices_covers_all_default_tickers():
    expected = {
        "AAPL",
        "GOOGL",
        "MSFT",
        "AMZN",
        "TSLA",
        "NVDA",
        "META",
        "JPM",
        "V",
        "NFLX",
    }
    assert set(SEED_PRICES.keys()) == expected


def test_ticker_params_covers_all_seed_tickers():
    assert set(TICKER_PARAMS.keys()) == set(SEED_PRICES.keys())


def test_known_tickers_matches_seed_prices():
    assert frozenset(SEED_PRICES.keys()) == KNOWN_TICKERS


def test_default_params_has_required_keys():
    assert "drift" in DEFAULT_PARAMS
    assert "vol" in DEFAULT_PARAMS
    assert "beta" in DEFAULT_PARAMS


def test_tick_returns_update_per_ticker():
    sim = GBMSimulator()
    sim.initialize(["AAPL", "MSFT"])
    updates = sim.tick()
    tickers = {u.ticker for u in updates}
    assert tickers == {"AAPL", "MSFT"}


def test_prices_always_positive():
    sim = GBMSimulator()
    sim.initialize(["TSLA"])  # high volatility
    for _ in range(500):
        updates = sim.tick()
        for u in updates:
            assert u.price > 0


def test_tick_empty_tickers_returns_empty():
    sim = GBMSimulator()
    sim.initialize([])
    assert sim.tick() == []


def test_add_ticker_starts_at_seed_price():
    sim = GBMSimulator()
    sim.initialize([])
    sim.add_ticker("AAPL")
    updates = sim.tick()
    assert len(updates) == 1
    # Price starts near seed price (190.0); after one tick should be very close
    assert abs(updates[0].prev_price - SEED_PRICES["AAPL"]) < 0.01


def test_add_unknown_ticker_uses_default_price():
    sim = GBMSimulator()
    sim.initialize([])
    sim.add_ticker("FOOBAR")
    updates = sim.tick()
    assert len(updates) == 1
    assert updates[0].prev_price == pytest.approx(100.0)


def test_remove_ticker_stops_updates():
    sim = GBMSimulator()
    sim.initialize(["AAPL", "MSFT"])
    sim.remove_ticker("AAPL")
    updates = sim.tick()
    tickers = {u.ticker for u in updates}
    assert "AAPL" not in tickers
    assert "MSFT" in tickers


def test_get_tickers_returns_current_set():
    sim = GBMSimulator()
    sim.initialize(["AAPL", "MSFT"])
    assert sim.get_tickers() == {"AAPL", "MSFT"}
    sim.add_ticker("TSLA")
    assert sim.get_tickers() == {"AAPL", "MSFT", "TSLA"}
    sim.remove_ticker("MSFT")
    assert sim.get_tickers() == {"AAPL", "TSLA"}


def test_update_prev_price_matches_prior_tick():
    sim = GBMSimulator()
    sim.initialize(["AAPL"])
    updates1 = sim.tick()
    price_after_tick1 = updates1[0].price
    updates2 = sim.tick()
    # prev_price in tick 2 should equal price from tick 1
    assert updates2[0].prev_price == pytest.approx(price_after_tick1)


def test_gbm_price_formula_valid():
    """Verify the GBM formula produces finite, positive prices."""
    sim = GBMSimulator()
    sim.initialize(["NVDA"])
    for _ in range(1000):
        updates = sim.tick()
        for u in updates:
            assert math.isfinite(u.price)
            assert u.price > 0


def test_duplicate_add_ticker_no_reset():
    """Adding the same ticker twice should not reset its price."""
    sim = GBMSimulator()
    sim.initialize(["AAPL"])
    # run a few ticks to move price away from seed
    for _ in range(10):
        sim.tick()
    price_before = sim._prices["AAPL"]
    sim.add_ticker("AAPL")  # duplicate add
    assert sim._prices["AAPL"] == pytest.approx(price_before)


def test_ticker_uppercase_normalisation():
    sim = GBMSimulator()
    sim.initialize(["aapl"])
    assert "AAPL" in sim.get_tickers()
