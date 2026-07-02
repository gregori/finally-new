"""Database query functions for FinAlly."""

import json
import uuid
from datetime import UTC, datetime

import aiosqlite

_USER_ID = "default"


async def get_user_profile(db: aiosqlite.Connection) -> dict | None:
    """Return the default user profile as a dict, or None if not found."""
    async with db.execute(
        "SELECT id, cash_balance, created_at FROM users_profile WHERE id = ?",
        (_USER_ID,),
    ) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def ensure_user_profile(db: aiosqlite.Connection) -> dict:
    """Get or create the default user profile, returning it as a dict."""
    profile = await get_user_profile(db)
    if profile is None:
        now = datetime.now(UTC).isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO users_profile "
            "(id, cash_balance, created_at) VALUES (?, ?, ?)",
            (_USER_ID, 10000.0, now),
        )
        await db.commit()
        profile = await get_user_profile(db)
    return profile  # type: ignore[return-value]


async def get_watchlist(db: aiosqlite.Connection) -> list[str]:
    """Return ordered list of watched ticker symbols."""
    async with db.execute(
        "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at ASC",
        (_USER_ID,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [row["ticker"] for row in rows]


async def add_to_watchlist(db: aiosqlite.Connection, ticker: str) -> None:
    """Add a ticker to the watchlist, silently ignoring duplicates."""
    now = datetime.now(UTC).isoformat()
    await db.execute(
        "INSERT OR IGNORE INTO watchlist "
        "(id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), _USER_ID, ticker, now),
    )
    await db.commit()


async def remove_from_watchlist(db: aiosqlite.Connection, ticker: str) -> None:
    """Remove a ticker from the watchlist."""
    await db.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (_USER_ID, ticker),
    )
    await db.commit()


async def get_positions(db: aiosqlite.Connection) -> list[dict]:
    """Return all open positions for the default user."""
    async with db.execute(
        "SELECT id, user_id, ticker, quantity, avg_cost, updated_at "
        "FROM positions WHERE user_id = ?",
        (_USER_ID,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def upsert_position(
    db: aiosqlite.Connection, ticker: str, quantity: float, avg_cost: float
) -> None:
    """Insert or update a position for the given ticker."""
    now = datetime.now(UTC).isoformat()
    await db.execute(
        """
        INSERT INTO positions
            (id, user_id, ticker, quantity, avg_cost, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, ticker) DO UPDATE SET
            quantity = excluded.quantity,
            avg_cost = excluded.avg_cost,
            updated_at = excluded.updated_at
        """,
        (str(uuid.uuid4()), _USER_ID, ticker, quantity, avg_cost, now),
    )
    await db.commit()


async def remove_position(db: aiosqlite.Connection, ticker: str) -> None:
    """Delete a position by ticker."""
    await db.execute(
        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
        (_USER_ID, ticker),
    )
    await db.commit()


async def record_trade(
    db: aiosqlite.Connection,
    ticker: str,
    side: str,
    quantity: float,
    price: float,
) -> None:
    """Append a trade record to the trade log."""
    now = datetime.now(UTC).isoformat()
    await db.execute(
        "INSERT INTO trades "
        "(id, user_id, ticker, side, quantity, price, executed_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), _USER_ID, ticker, side, quantity, price, now),
    )
    await db.commit()


async def get_portfolio_snapshots(
    db: aiosqlite.Connection, limit: int = 500
) -> list[dict]:
    """Return portfolio value snapshots ordered by recorded_at ASC."""
    async with db.execute(
        "SELECT id, user_id, total_value, recorded_at "
        "FROM portfolio_snapshots "
        "WHERE user_id = ? ORDER BY recorded_at ASC LIMIT ?",
        (_USER_ID, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def record_portfolio_snapshot(
    db: aiosqlite.Connection, total_value: float
) -> None:
    """Record a portfolio total value snapshot."""
    now = datetime.now(UTC).isoformat()
    await db.execute(
        "INSERT INTO portfolio_snapshots "
        "(id, user_id, total_value, recorded_at) VALUES (?, ?, ?, ?)",
        (str(uuid.uuid4()), _USER_ID, total_value, now),
    )
    await db.commit()


async def get_chat_messages(
    db: aiosqlite.Connection, limit: int = 50
) -> list[dict]:
    """Return chat messages ordered by created_at ASC."""
    async with db.execute(
        "SELECT id, user_id, role, content, actions, created_at "
        "FROM chat_messages "
        "WHERE user_id = ? ORDER BY created_at ASC LIMIT ?",
        (_USER_ID, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def save_chat_message(
    db: aiosqlite.Connection,
    role: str,
    content: str,
    actions: dict | None = None,
) -> None:
    """Persist a chat message, serializing actions to JSON if provided."""
    now = datetime.now(UTC).isoformat()
    actions_json = json.dumps(actions) if actions is not None else None
    await db.execute(
        "INSERT INTO chat_messages "
        "(id, user_id, role, content, actions, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), _USER_ID, role, content, actions_json, now),
    )
    await db.commit()
