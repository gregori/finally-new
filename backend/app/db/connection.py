"""Database connection and initialization for FinAlly."""

import os
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import aiosqlite

DB_PATH = os.getenv("DATABASE_URL", "/app/db/finally.db")

_DEFAULT_TICKERS = [
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


async def _setup_schema(db: aiosqlite.Connection) -> None:
    """Create tables and seed default data on a given connection."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS users_profile (
            id TEXT PRIMARY KEY,
            cash_balance REAL DEFAULT 10000.0,
            created_at TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            ticker TEXT,
            added_at TEXT,
            UNIQUE(user_id, ticker)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            ticker TEXT,
            quantity REAL,
            avg_cost REAL,
            updated_at TEXT,
            UNIQUE(user_id, ticker)
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            ticker TEXT,
            side TEXT,
            quantity REAL,
            price REAL,
            executed_at TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            total_value REAL,
            recorded_at TEXT
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT 'default',
            role TEXT,
            content TEXT,
            actions TEXT,
            created_at TEXT
        )
    """)

    now = datetime.now(UTC).isoformat()

    await db.execute(
        "INSERT OR IGNORE INTO users_profile "
        "(id, cash_balance, created_at) VALUES (?, ?, ?)",
        ("default", 10000.0, now),
    )

    for ticker in _DEFAULT_TICKERS:
        await db.execute(
            "INSERT OR IGNORE INTO watchlist "
            "(id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), "default", ticker, now),
        )

    await db.commit()


async def init_db(db: aiosqlite.Connection | None = None) -> None:
    """
    Initialize database schema and seed default data.

    Safe to call multiple times — uses IF NOT EXISTS and INSERT OR IGNORE.
    Accepts an optional connection for in-memory testing.
    """
    if db is None:
        async with aiosqlite.connect(DB_PATH) as conn:
            await _setup_schema(conn)
    else:
        await _setup_schema(db)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Async context manager yielding a database connection."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
