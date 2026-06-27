import os

from .interface import MarketDataSource
from .massive_client import MassiveDataSource
from .simulator import SimulatorDataSource


def create_market_data_source() -> MarketDataSource:
    """Return the active market data provider based on environment variables.

    Uses MassiveDataSource when MASSIVE_API_KEY is set and non-empty.
    Falls back to SimulatorDataSource when the key is absent or empty.
    This is the single decision point — no other code should check MASSIVE_API_KEY.
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key)
    return SimulatorDataSource()
