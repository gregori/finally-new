import asyncio
import contextlib
import logging
import math
import random

from .cache import PriceCache
from .interface import MarketDataSource
from .models import PriceUpdate
from .seed_prices import DEFAULT_PARAMS, SEED_PRICES, TICKER_PARAMS

logger = logging.getLogger(__name__)

TICK_INTERVAL_S = 0.5
TRADING_DAYS_PER_YEAR = 252
TRADING_HOURS_PER_DAY = 6.5
DT = TICK_INTERVAL_S / (TRADING_DAYS_PER_YEAR * TRADING_HOURS_PER_DAY * 3600)
# ~0.1% chance per ticker per tick → roughly one event every 30 real seconds
# across all tickers
EVENT_PROBABILITY = TICK_INTERVAL_S / (
    TRADING_DAYS_PER_YEAR * TRADING_HOURS_PER_DAY * 3600 / 30
)

KNOWN_TICKERS: frozenset[str] = frozenset(SEED_PRICES.keys())


class GBMSimulator:
    """
    Geometric Brownian Motion price engine with a shared correlated market
    factor.

    Each tick generates one market_factor shared across all tickers, mixed with
    per-ticker idiosyncratic noise scaled by beta. This produces realistic
    sector co-movement: tech stocks (β≈0.7) move together on macro events,
    while defensive names (β≈0.3) are more idiosyncratic.
    """

    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._tickers: set[str] = set()
        # Use SystemRandom which sources from the OS CSPRNG instead of the
        # default Mersenne Twister. This makes randomness suitable for cases
        # where stronger unpredictability is desired.
        self._rng = random.SystemRandom()

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
        """
        Advance all prices by one 500ms step and return the resulting updates.
        """
        if not self._tickers:
            return []

        market_factor = self._rng.gauss(0, 1)
        updates: list[PriceUpdate] = []

        for ticker in list(self._tickers):
            params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
            drift = params["drift"]
            vol = params["vol"]
            beta = params["beta"]

            prev_price = self._prices[ticker]
            noise = self._rng.gauss(0, 1)
            z = beta * market_factor + math.sqrt(1 - beta**2) * noise
            new_price = prev_price * math.exp(
                (drift - 0.5 * vol**2) * DT + vol * math.sqrt(DT) * z
            )

            if self._rng.random() < EVENT_PROBABILITY:
                direction = self._rng.choice([-1, 1])
                magnitude = self._rng.uniform(0.02, 0.05)
                new_price *= 1 + direction * magnitude

            new_price = max(new_price, 0.01)
            self._prices[ticker] = new_price
            updates.append(
                PriceUpdate.from_prices(ticker, new_price, prev_price)
            )

        return updates


class SimulatorDataSource(MarketDataSource):
    """
    MarketDataSource backed by the GBM simulator.
    Default when no API key is set.
    """

    def __init__(self) -> None:
        self._simulator = GBMSimulator()
        self._cache = PriceCache()
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._simulator.initialize(tickers)
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    def get_price(self, ticker: str) -> PriceUpdate | None:
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
        max_ticker_length = 5
        return bool(t) and t.isalpha() and 1 <= len(t) <= max_ticker_length

    def get_tickers(self) -> set[str]:
        return self._simulator.get_tickers()

    @property
    def version(self) -> int:
        return self._cache.version

    async def _tick_loop(self) -> None:
        while True:
            try:
                updates = self._simulator.tick()
                if updates:
                    await self._cache.set_many(updates)
            except Exception:
                logger.exception("Unexpected error in simulator tick loop")
            await asyncio.sleep(TICK_INTERVAL_S)
