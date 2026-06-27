"""Unit tests for PriceUpdate model."""
import time

import pytest

from app.market.models import PriceUpdate


def test_from_prices_positive_change():
    update = PriceUpdate.from_prices("AAPL", 191.0, 190.0)
    assert update.ticker == "AAPL"
    assert update.price == 191.0
    assert update.prev_price == 190.0
    assert update.change == pytest.approx(1.0)
    assert update.change_pct == pytest.approx(1.0 / 190.0 * 100)


def test_from_prices_negative_change():
    update = PriceUpdate.from_prices("TSLA", 245.0, 250.0)
    assert update.change == pytest.approx(-5.0)
    assert update.change_pct == pytest.approx(-5.0 / 250.0 * 100)


def test_from_prices_no_change():
    update = PriceUpdate.from_prices("MSFT", 415.0, 415.0)
    assert update.change == pytest.approx(0.0)
    assert update.change_pct == pytest.approx(0.0)


def test_from_prices_zero_prev_price():
    # change_pct must not divide by zero
    update = PriceUpdate.from_prices("AAPL", 100.0, 0.0)
    assert update.change_pct == 0.0


def test_from_prices_timestamp_is_recent():
    before = time.time()
    update = PriceUpdate.from_prices("AAPL", 190.0, 189.0)
    after = time.time()
    assert before <= update.timestamp <= after


def test_ticker_stored_as_given():
    update = PriceUpdate.from_prices("NVDA", 875.0, 870.0)
    assert update.ticker == "NVDA"


def test_price_stored_correctly():
    update = PriceUpdate.from_prices("V", 285.50, 284.0)
    assert update.price == pytest.approx(285.50)


def test_prev_price_stored_correctly():
    update = PriceUpdate.from_prices("JPM", 200.0, 198.5)
    assert update.prev_price == pytest.approx(198.5)


def test_frozen_dataclass_immutable():
    update = PriceUpdate.from_prices("AAPL", 190.0, 189.0)
    with pytest.raises((AttributeError, TypeError)):
        update.price = 999.0  # type: ignore[misc]


def test_direct_construction():
    update = PriceUpdate(
        ticker="META",
        price=500.0,
        prev_price=495.0,
        timestamp=1000.0,
        change=5.0,
        change_pct=1.01010,
    )
    assert update.ticker == "META"
    assert update.price == 500.0
    assert update.prev_price == 495.0
    assert update.timestamp == 1000.0


def test_change_pct_large_move():
    # 10% gain
    update = PriceUpdate.from_prices("TSLA", 275.0, 250.0)
    assert update.change_pct == pytest.approx(10.0)
