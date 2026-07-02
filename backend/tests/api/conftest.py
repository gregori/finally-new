# ruff: noqa: I001
"""Test configuration and fixtures for API route tests.

Environment variables must be set before any app.* imports because several
modules read config at import time (e.g. DB_PATH in connection.py).
"""

import asyncio
import os
import tempfile
from pathlib import Path

# --- env setup (must precede all app imports) ---
# Force simulator by clearing MASSIVE_API_KEY before load_dotenv runs.
_TEST_DB = str(Path(tempfile.gettempdir()) / "finally_test.db")
os.environ["MASSIVE_API_KEY"] = ""  # force simulator, override .env
os.environ.setdefault("OPENCODE_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL", _TEST_DB)
os.environ.setdefault("LLM_MOCK", "true")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_db
from app.main import app
from app.market import create_market_data_source
from app.market.seed_prices import SEED_PRICES


def _db_path() -> Path | None:
    val = os.environ.get("DATABASE_URL", "")
    return Path(val) if val and val != ":memory:" else None


@pytest.fixture
async def client():
    """Fresh AsyncClient with database and market source initialised.

    httpx's ASGITransport does not trigger the ASGI lifespan protocol, so
    this fixture sets up app state (database + market source) directly before
    handing the client to the test.
    """
    # Start from a clean database
    db_file = _db_path()
    if db_file and db_file.exists():
        db_file.unlink()
    await init_db()

    # Start market data source and attach to app state
    source = create_market_data_source()
    await source.start(list(SEED_PRICES.keys()))
    app.state.source = source

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c

    # Teardown
    await source.stop()
    if db_file and db_file.exists():
        db_file.unlink()


@pytest.fixture
async def client_with_prices(client):
    """Like client, but waits for the simulator to populate the price cache."""
    await asyncio.sleep(0.6)
    return client
