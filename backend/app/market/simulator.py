import asyncio
import math
import random
from typing import Optional

from .cache import PriceCache
from .interface import MarketDataSource
from .models import PriceUpdate
from .seed_prices import DEFAULT_PARAMS, SEED_PRICES, TICKER_PARAMS

TICK_INTERVAL_S = 0.5
TRADING_DAYS_PER_YEAR = 252
TRADING_HOURS_PER_DAY = 6.5
DT = TICK_INTERVAL_S / (TRADING_DAYS_PER_YEAR * TRADING_HOURS_PER_DAY * 3600)
# ~0.1% chance per ticker per tick → roughly one event every 30 real seconds across all tickers
EVENT_PROBABILITY = TICK_INTERVAL_S / (TRADING_DAYS_PER_YEAR * TRADING_HOURS_PER_DAY * 3600 / 30)

KNOWN_TICKERS: frozenset[str] = frozenset(SEED_PRICES.keys())


class GBMSimulator:
    """Geometric Brownian Motion price engine with a shared correlated market factor.

    Each tick generates one market_factor shared across all tickers, mixed with
    per-ticker idiosyncratic noise scaled by beta. This produces realistic
    sector co-movement: tech stocks (β≈0.7) move together on macro events,
    while defensive names (β≈0.3) are more idiosyncratic.
    """

    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._tickers: set[str] = set()

    def initialize(self, tickers: list[str]) -> None:
        self._tickers = {t.upper() for t in tickers}
        for ticker in self._tickers:
            self._prices[ticker] = SEED_PRICES.get(ticker, 100.0)

    def add_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        if ticker not in self._tickers:
            self._tickers.add(ticker)
            self._prices[ticker] = SEED_PRICES.get(ticker, 100.0)

    def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tickers.discard(ticker)
        self._prices.pop(ticker, None)

    def get_tickers(self) -> set[str]:
        return set(self._tickers)

    def tick(self) -> list[PriceUpdate]:
        """Advance all prices by one 500ms step and return the resulting updates."""
        if not self._tickers:
            return []

        market_factor = random.gauss(0, 1)
        updates: list[PriceUpdate] = []

        for ticker in list(self._tickers):
            params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
            drift = params["drift"]
            vol = params["vol"]
            beta = params["beta"]

            prev_price = self._prices[ticker]
            noise = random.gauss(0, 1)
            z = beta * market_factor + math.sqrt(1 - beta**2) * noise
            new_price = prev_price * math.exp(
                (drift - 0.5 * vol**2) * DT + vol * math.sqrt(DT) * z
            )

            if random.random() < EVENT_PROBABILITY:
                direction = random.choice([-1, 1])
                magnitude = random.uniform(0.02, 0.05)
                new_price *= 1 + direction * magnitude

            new_price = max(new_price, 0.01)
            self._prices[ticker] = new_price
            updates.append(PriceUpdate.from_prices(ticker, new_price, prev_price))

        return updates


class SimulatorDataSource(MarketDataSource):
    """MarketDataSource backed by the GBM simulator. Default when no API key is set."""

    def __init__(self) -> None:
        self._simulator = GBMSimulator()
        self._cache = PriceCache()
        self._task: Optional[asyncio.Task] = None

    async def start(self, tickers: list[str]) -> None:
        self._simulator.initialize(tickers)
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def get_price(self, ticker: str) -> Optional[PriceUpdate]:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceUpdate]:
        return self._cache.get_all()

    async def add_ticker(self, ticker: str) -> None:
        self._simulator.add_ticker(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._simulator.remove_ticker(ticker)
        await self._cache.remove(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        t = ticker.upper().strip()
        return bool(t) and t.isalpha() and 1 <= len(t) <= 5

    def get_tickers(self) -> set[str]:
        return self._simulator.get_tickers()

    async def _tick_loop(self) -> None:
        while True:
            updates = self._simulator.tick()
            if updates:
                await self._cache.set_many(updates)
            await asyncio.sleep(TICK_INTERVAL_S)
