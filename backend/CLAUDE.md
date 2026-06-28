# Backend — Developer Guide

FastAPI backend for FinAlly. Managed as a `uv` project (Python 3.12+). All server logic lives here: database init, API routes, SSE streaming, market data, and LLM integration.

## Running

All commands use `uv` — it reads `pyproject.toml` and manages the virtualenv automatically. No manual `pip install` or `venv` activation needed.

```bash
# Install / sync dependencies (run once, or after changing pyproject.toml)
uv sync --dev

# Tests
uv run pytest tests/ -v

# Tests with coverage
uv run pytest tests/ --cov=app --cov-report=term-missing

# Lint / format check
uv run ruff check app/ tests/
uv run ruff format --check app/ tests/

# Market data demo (terminal dashboard)
uv run python market_data_demo.py
uv run python market_data_demo.py --duration 120
uv run python market_data_demo.py --tickers AAPL TSLA NVDA
```

In production the app runs via uvicorn inside Docker — see the root `Dockerfile`.

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   └── market/           # Market data subsystem (COMPLETE — see planning/MARKET_DATA_SUMMARY.md)
│       ├── __init__.py   # Public exports
│       ├── models.py     # PriceUpdate dataclass
│       ├── interface.py  # MarketDataSource ABC
│       ├── cache.py      # PriceCache (thread-safe, version-tracked)
│       ├── seed_prices.py# Seed prices + GBM params per ticker
│       ├── simulator.py  # GBMSimulator + SimulatorDataSource
│       ├── massive_client.py # MassiveDataSource (Polygon.io REST)
│       ├── factory.py    # create_market_data_source() — reads MASSIVE_API_KEY
│       └── stream.py     # create_stream_router() — FastAPI SSE factory
├── tests/
│   └── market/           # 82 tests, 86% coverage, all passing
├── market_data_demo.py   # Rich terminal demo
└── pyproject.toml
```

## Environment Variables

Read from `.env` at the project root (one directory up from `backend/`). The backend uses `python-dotenv` to load it.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENCODE_API_KEY` | Yes | — | LLM chat via OpenCode → Cerebras |
| `MASSIVE_API_KEY` | No | `""` | Real market data (Polygon.io). Empty = use simulator |
| `LLM_MOCK` | No | `false` | Return deterministic mock LLM responses for E2E tests |

The backend **fails fast at startup** if `OPENCODE_API_KEY` is absent.

## Market Data (Complete)

See `planning/MARKET_DATA_SUMMARY.md` for full documentation.

Quick import:
```python
from app.market import PriceCache, create_market_data_source, create_stream_router
```

The factory selects simulator vs. Massive automatically from `MASSIVE_API_KEY`. Wire into FastAPI lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = PriceCache()
    source = create_market_data_source(cache)
    await source.start(initial_tickers)
    app.state.market = source
    app.state.cache = cache
    yield
    await source.stop()
```

## API Response Envelope

Every endpoint returns this shape:
```json
{"success": true,  "data": { ... }}
{"success": false, "error": "Human-readable message", "code": "MACHINE_CODE"}
```

## Database

SQLite at `/app/db/finally.db` (runtime Docker volume). The backend creates the schema and seeds default data on startup if the file is missing or empty — no separate migration step.

Tables: `users_profile`, `watchlist`, `positions`, `trades`, `portfolio_snapshots`, `chat_messages`. All have `user_id TEXT DEFAULT "default"` for future multi-user support.

**All SQL queries must use parameterized statements** — raw string interpolation in SQL is never acceptable.

## LLM Integration

Uses the `cerebras` skill: LiteLLM → OpenCode Go → Cerebras → `opencode/deepseek-v4-flash-free`.

```python
import os
from litellm import completion

MODEL    = "opencode/deepseek-v4-flash-free"
API_BASE = "https://opencode.ai/zen/v1"
API_KEY  = os.environ["OPENCODE_API_KEY"]
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

response = completion(
    model=MODEL,
    messages=messages,
    response_format=MyPydanticModel,   # structured output
    reasoning_effort="low",
    extra_body=EXTRA_BODY,
    api_base=API_BASE,
    api_key=API_KEY,
    timeout=30,
)
```

Timeout: 30s. Retry up to 2 times before returning an error to the user. When `LLM_MOCK=true`, skip the call and return a hardcoded response.

## Dependencies

Key packages (see `pyproject.toml` for pinned versions):

| Package | Purpose |
|---------|---------|
| `fastapi` | Web framework + dependency injection |
| `uvicorn[standard]` | ASGI server |
| `pydantic` | Data validation + structured LLM outputs |
| `httpx` | Async HTTP (Massive API polling) |
| `litellm` | LLM client library |
| `aiosqlite` | Async SQLite |
| `sse-starlette` | SSE streaming helpers |
| `python-dotenv` | `.env` loading |

Dev: `pytest`, `pytest-asyncio`, `pytest-cov`, `rich` (demo), `ruff` (lint/format).
