"""Unit tests for the market data source factory."""
import os
from unittest.mock import patch

import pytest

from app.market.factory import create_market_data_source
from app.market.massive_client import MassiveDataSource
from app.market.simulator import SimulatorDataSource


def test_no_key_returns_simulator():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        source = create_market_data_source()
    assert isinstance(source, SimulatorDataSource)


def test_empty_key_returns_simulator():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
        source = create_market_data_source()
    assert isinstance(source, SimulatorDataSource)


def test_whitespace_only_key_returns_simulator():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        source = create_market_data_source()
    assert isinstance(source, SimulatorDataSource)


def test_valid_key_returns_massive():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "test_key_123"}):
        source = create_market_data_source()
    assert isinstance(source, MassiveDataSource)


def test_massive_source_receives_api_key():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "my_secret_key"}):
        source = create_market_data_source()
    assert isinstance(source, MassiveDataSource)
    assert source._api_key == "my_secret_key"


def test_simulator_implements_interface():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        source = create_market_data_source()
    from app.market.interface import MarketDataSource
    assert isinstance(source, MarketDataSource)


def test_massive_implements_interface():
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "abc123"}):
        source = create_market_data_source()
    from app.market.interface import MarketDataSource
    assert isinstance(source, MarketDataSource)
