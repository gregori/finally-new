"""Shared pytest fixtures for the FinAlly backend test suite."""

import pytest


@pytest.fixture
def default_tickers() -> list[str]:
    return [
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
    ]
