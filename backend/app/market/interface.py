from abc import ABC, abstractmethod

from .models import PriceUpdate


class MarketDataSource(ABC):
    """Abstract base class for all market data providers."""

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Start the provider with an initial set of tickers. Non-blocking."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task and release resources."""

    @abstractmethod
    def get_price(self, ticker: str) -> PriceUpdate | None:
        """
        Return the latest price update for a ticker, or None if unavailable.
        """

    @abstractmethod
    def get_all_prices(self) -> dict[str, PriceUpdate]:
        """Return a snapshot copy of all latest prices."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Add a ticker to the tracked set."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Remove a ticker from the tracked set."""

    @abstractmethod
    async def validate_ticker(self, ticker: str) -> bool:
        """Return True if the ticker is a known, tradeable symbol."""

    def get_tickers(self) -> set[str]:
        """Return the set of currently tracked ticker symbols."""
        return set(self.get_all_prices().keys())
