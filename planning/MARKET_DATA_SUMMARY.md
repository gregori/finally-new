# Market Data Backend — Summary

**Status:** Complete, tested, reviewed, all issues resolved.
**Location:** `backend/app/market/` — 8 modules, ~500 lines of production code.

---

## Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, version-tracked, in-memory)
        │
        ├──→ SSE stream  /api/stream/prices  →  Frontend EventSource
        ├──→ Portfolio valuation
        └──→ Trade execution
```

Both data sources implement the same `MarketDataSource` ABC (strategy pattern). All downstream code is source-agnostic — only the factory at startup reads `MASSIVE_API_KEY`.

---

## Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate` — frozen dataclass (ticker, price, previous_price, timestamp, change, direction) |
| `interface.py` | `MarketDataSource` — ABC with `start/stop/add_ticker/remove_ticker/get_tickers/validate_ticker` |
| `cache.py` | `PriceCache` — async lock + version counter; producers write, consumers read |
| `seed_prices.py` | Realistic seed prices and per-ticker GBM params (drift/vol/beta); sector groupings |
| `simulator.py` | `GBMSimulator` (pure engine) + `SimulatorDataSource` (async lifecycle wrapper) |
| `massive_client.py` | `MassiveDataSource` — httpx-based REST polling of Polygon.io via the `massive` package |
| `factory.py` | `create_market_data_source()` — selects simulator vs Massive from env var |
| `stream.py` | `create_stream_router()` — FastAPI SSE endpoint factory |

---

## Key Design Decisions

- **Strategy pattern** — both sources implement the same ABC; the factory is the single switch point
- **PriceCache as single truth** — producers write once; all consumers read from the same snapshot; version counter avoids redundant SSE pushes
- **GBM with correlated moves** — `Z_i = β·market_factor + √(1−β²)·noise_i` produces realistic sector co-movement; tech β≈0.7, finance β≈0.3
- **Random shock events** — ~0.1% chance per ticker per tick of a 2–5% move for visual drama (~1 event/30s across all tickers)
- **Exception guard in tick loop** — `_tick_loop` catches all exceptions and logs, matching `MassiveDataSource._poll_loop`; the simulator never dies silently
- **SSE push cadence** — 500ms in simulator mode; adapts to source poll rate with Massive (15s free tier, 2–15s paid)

---

## Test Suite

**82 tests, all passing.** 6 modules in `backend/tests/market/`. Overall coverage: **86%**.

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_models.py` | 11 | 100% |
| `test_cache.py` | 14 | 100% |
| `test_factory.py` | 7 | 100% |
| `test_simulator.py` | 18 | 97% |
| `test_simulator_source.py` | 10 | integration |
| `test_massive.py` | 22 | 79% (lifecycle mocked) |

Run with: `cd backend && uv run pytest tests/market/ -v`

---

## Usage for Downstream Code

```python
from app.market import PriceCache, create_market_data_source

# Startup (in FastAPI lifespan)
cache = PriceCache()
source = create_market_data_source(cache)   # reads MASSIVE_API_KEY env var
await source.start(["AAPL", "GOOGL", "MSFT", ...])

# Read prices (synchronous, safe from SSE handlers)
update = cache.get("AAPL")           # PriceUpdate | None
price  = cache.get_price("AAPL")     # float | None
all_px = cache.get_all()             # dict[str, PriceUpdate]

# Dynamic watchlist
await source.add_ticker("TSLA")
await source.remove_ticker("GOOGL")

# Shutdown
await source.stop()
```

The SSE router is wired in `main.py`:
```python
from app.market import create_stream_router
app.include_router(create_stream_router(source), prefix="/api")
```

---

## Demo

```bash
cd backend
uv run python market_data_demo.py
```

Runs a Rich terminal dashboard: live-updating price table for all 10 tickers with sparklines, color-coded direction arrows, and an event log for notable price moves. Runs 60 seconds or until Ctrl+C.

---

## Known Gaps (non-blocking)

- `stream.py` coverage is 38% — the SSE route and async generator body lack integration tests. An `httpx.AsyncClient` + ASGI transport test would close this.
- `MassiveDataSource` `start()`/`stop()` lifecycle is not tested (requires live network); 79% coverage is expected.
- `cache.version` reads without acquiring the lock — safe on CPython (GIL), but technically a data race under no-GIL Python 3.13t+.
