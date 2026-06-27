import asyncio
from typing import Optional

from .models import PriceUpdate


class PriceCache:
    """Thread-safe in-memory cache of latest prices per ticker.

    Producers (simulator/Massive poller) write via set/set_many.
    Consumers (SSE handlers, API routes) read via get/get_all.
    The version counter increments on every write batch, enabling
    SSE handlers to detect changes without comparing price values.
    """

    def __init__(self) -> None:
        self._data: dict[str, PriceUpdate] = {}
        self._lock = asyncio.Lock()
        self._version: int = 0

    async def set(self, update: PriceUpdate) -> None:
        async with self._lock:
            self._data[update.ticker] = update
            self._version += 1

    async def set_many(self, updates: list[PriceUpdate]) -> None:
        async with self._lock:
            for update in updates:
                self._data[update.ticker] = update
            if updates:
                self._version += 1

    def get(self, ticker: str) -> Optional[PriceUpdate]:
        return self._data.get(ticker)

    def get_price(self, ticker: str) -> Optional[float]:
        update = self._data.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        return dict(self._data)

    @property
    def version(self) -> int:
        return self._version

    async def remove(self, ticker: str) -> None:
        async with self._lock:
            self._data.pop(ticker, None)
            self._version += 1
