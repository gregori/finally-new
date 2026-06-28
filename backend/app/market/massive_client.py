import asyncio
import contextlib
import logging
from http import HTTPStatus

import httpx

from .cache import PriceCache
from .interface import MarketDataSource
from .models import PriceUpdate

logger = logging.getLogger(__name__)

BASE_URL = "https://api.polygon.io"
FREE_TIER_POLL_INTERVAL_S = 15.0


class MassiveDataSource(MarketDataSource):
    """
    MarketDataSource that polls the Massive (Polygon.io) REST API.

    Uses the v2 snapshot endpoint which accepts a comma-separated ticker list,
    fetching all watched tickers in a single request per poll cycle.
    Falls back gracefully on rate-limit (429) and auth (403) errors.
    """

    def __init__(
        self, api_key: str, poll_interval_s: float = FREE_TIER_POLL_INTERVAL_S
    ) -> None:
        self._api_key = api_key
        self._poll_interval_s = poll_interval_s
        self._cache = PriceCache()
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self, tickers: list[str]) -> None:
        self._tickers = {t.upper() for t in tickers}
        self._client = httpx.AsyncClient(timeout=10.0)
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_price(self, ticker: str) -> PriceUpdate | None:
        return self._cache.get(ticker.upper())

    def get_all_prices(self) -> dict[str, PriceUpdate]:
        return self._cache.get_all()

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker.upper())

    async def remove_ticker(self, ticker: str) -> None:
        ticker = ticker.upper()
        self._tickers.discard(ticker)
        await self._cache.remove(ticker)

    async def validate_ticker(self, ticker: str) -> bool:
        """Check the ticker against Polygon's reference endpoint."""
        ticker = ticker.upper().strip()
        max_ticker_lenght = 5
        if (
            not ticker
            or not ticker.isalpha()
            or len(ticker) > max_ticker_lenght
        ):
            return False
        if self._client is None:
            return False
        try:
            url = f"{BASE_URL}/v3/reference/tickers/{ticker}"
            resp = await self._client.get(
                url, params={"apiKey": self._api_key}
            )
            if resp.status_code == HTTPStatus.OK:
                return resp.json().get("status") == "OK"
        except httpx.HTTPError:
            return False
        else:
            return False

    def get_tickers(self) -> set[str]:
        return set(self._tickers)

    async def _poll_loop(self) -> None:
        while True:
            if self._tickers:
                await self._poll_once()
            await asyncio.sleep(self._poll_interval_s)

    async def _poll_once(self) -> None:
        if not self._client or not self._tickers:
            return
        tickers_str = ",".join(sorted(self._tickers))
        url = f"{BASE_URL}/v2/snapshot/locale/us/markets/stocks/tickers"
        params = {"tickers": tickers_str, "apiKey": self._api_key}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            updates = self._parse_snapshots(data.get("tickers", []))
            if updates:
                await self._cache.set_many(updates)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == HTTPStatus.TOO_MANY_REQUESTS:
                logger.warning(
                    "Massive API rate limit exceeded; "
                    "backing off one extra cycle"
                )
                await asyncio.sleep(self._poll_interval_s)
            elif status == HTTPStatus.FORBIDDEN:
                logger.exception(
                    "Massive API rejected request: invalid MASSIVE_API_KEY"
                )
            else:
                logger.warning("Massive API HTTP error %s: %s", status, exc)
        except httpx.TimeoutException:
            logger.warning("Massive API poll timed out; skipping cycle")
        except (httpx.HTTPError, ValueError) as exc:
            # Handle remaining HTTP-related errors and JSON/decoding errors.
            # Let asyncio.CancelledError propagate so task cancellation works
            # as expected.
            logger.warning("Massive API poll failed unexpectedly: %s", exc)

    def _parse_snapshots(self, snapshots: list[dict]) -> list[PriceUpdate]:
        updates: list[PriceUpdate] = []
        for snap in snapshots:
            ticker = snap.get("ticker", "")
            if not ticker:
                continue
            try:
                price, prev_price = self._extract_prices(snap)
                updates.append(
                    PriceUpdate.from_prices(ticker, price, prev_price)
                )
            except (KeyError, TypeError, ValueError):
                logger.warning("Could not parse snapshot for %s", ticker)
        return updates

    @staticmethod
    def _extract_prices(snap: dict) -> tuple[float, float]:
        """
        Extract current price and previous close from a Polygon snapshot dict.

        Prefers lastTrade.p (most current trade) over day.c (session close).
        prev_price is always the previous session close (prevDay.c).
        """
        last_trade = snap.get("lastTrade") or {}
        price = last_trade.get("p") or snap["day"]["c"]
        prev_price = snap["prevDay"]["c"]
        return float(price), float(prev_price)
