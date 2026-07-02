"""Tests for database query functions."""

import json

import aiosqlite
import pytest
from app.db import queries
from app.db.connection import init_db


@pytest.fixture
async def db():
    """In-memory database fixture with schema and seed data initialized."""
    async with aiosqlite.connect(":memory:") as conn:
        conn.row_factory = aiosqlite.Row
        await init_db(conn)
        yield conn


# --- User profile ---


async def test_get_user_profile_returns_seeded_default(db):
    profile = await queries.get_user_profile(db)
    assert profile is not None
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0
    assert profile["created_at"] is not None


async def test_ensure_user_profile_returns_existing(db):
    profile = await queries.ensure_user_profile(db)
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0


async def test_ensure_user_profile_creates_when_missing(db):
    await db.execute("DELETE FROM users_profile WHERE id = 'default'")
    await db.commit()

    profile = await queries.ensure_user_profile(db)
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0


# --- Watchlist ---


async def test_get_watchlist_returns_all_default_tickers(db):
    tickers = await queries.get_watchlist(db)
    assert len(tickers) == 10
    assert "AAPL" in tickers
    assert "NVDA" in tickers
    assert "NFLX" in tickers


async def test_add_to_watchlist(db):
    await queries.add_to_watchlist(db, "PYPL")
    tickers = await queries.get_watchlist(db)
    assert "PYPL" in tickers
    assert len(tickers) == 11


async def test_add_duplicate_ticker_is_ignored(db):
    await queries.add_to_watchlist(db, "AAPL")
    tickers = await queries.get_watchlist(db)
    assert tickers.count("AAPL") == 1


async def test_remove_from_watchlist(db):
    await queries.remove_from_watchlist(db, "AAPL")
    tickers = await queries.get_watchlist(db)
    assert "AAPL" not in tickers
    assert len(tickers) == 9


async def test_remove_nonexistent_ticker_does_not_raise(db):
    await queries.remove_from_watchlist(db, "NONEXISTENT")
    tickers = await queries.get_watchlist(db)
    assert len(tickers) == 10


# --- Positions ---


async def test_get_positions_empty(db):
    positions = await queries.get_positions(db)
    assert positions == []


async def test_upsert_position_creates_new(db):
    await queries.upsert_position(db, "AAPL", 10.0, 150.0)
    positions = await queries.get_positions(db)
    assert len(positions) == 1
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["quantity"] == 10.0
    assert positions[0]["avg_cost"] == 150.0


async def test_upsert_position_updates_existing(db):
    await queries.upsert_position(db, "AAPL", 10.0, 150.0)
    await queries.upsert_position(db, "AAPL", 20.0, 155.0)
    positions = await queries.get_positions(db)
    assert len(positions) == 1
    assert positions[0]["quantity"] == 20.0
    assert positions[0]["avg_cost"] == 155.0


async def test_upsert_multiple_positions(db):
    await queries.upsert_position(db, "AAPL", 10.0, 150.0)
    await queries.upsert_position(db, "TSLA", 5.0, 200.0)
    positions = await queries.get_positions(db)
    assert len(positions) == 2
    tickers = {p["ticker"] for p in positions}
    assert tickers == {"AAPL", "TSLA"}


async def test_remove_position(db):
    await queries.upsert_position(db, "AAPL", 10.0, 150.0)
    await queries.remove_position(db, "AAPL")
    positions = await queries.get_positions(db)
    assert positions == []


async def test_remove_nonexistent_position_does_not_raise(db):
    await queries.remove_position(db, "NONEXISTENT")
    positions = await queries.get_positions(db)
    assert positions == []


# --- Trades ---


async def test_record_trade_buy(db):
    await queries.record_trade(db, "AAPL", "buy", 10.0, 150.0)
    async with db.execute(
        "SELECT * FROM trades WHERE user_id = 'default'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 1
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["side"] == "buy"
    assert rows[0]["quantity"] == 10.0
    assert rows[0]["price"] == 150.0
    assert rows[0]["executed_at"] is not None


async def test_record_multiple_trades(db):
    await queries.record_trade(db, "AAPL", "buy", 10.0, 150.0)
    await queries.record_trade(db, "TSLA", "sell", 5.0, 220.0)
    async with db.execute(
        "SELECT * FROM trades WHERE user_id = 'default'"
    ) as cursor:
        rows = await cursor.fetchall()
    assert len(rows) == 2


# --- Portfolio snapshots ---


async def test_get_snapshots_empty(db):
    snapshots = await queries.get_portfolio_snapshots(db)
    assert snapshots == []


async def test_record_and_get_snapshot(db):
    await queries.record_portfolio_snapshot(db, 10500.0)
    snapshots = await queries.get_portfolio_snapshots(db)
    assert len(snapshots) == 1
    assert snapshots[0]["total_value"] == 10500.0
    assert snapshots[0]["recorded_at"] is not None


async def test_snapshots_ordered_asc(db):
    await queries.record_portfolio_snapshot(db, 10000.0)
    await queries.record_portfolio_snapshot(db, 10500.0)
    await queries.record_portfolio_snapshot(db, 11000.0)
    snapshots = await queries.get_portfolio_snapshots(db)
    values = [s["total_value"] for s in snapshots]
    assert values == [10000.0, 10500.0, 11000.0]


async def test_snapshots_limit(db):
    for i in range(10):
        await queries.record_portfolio_snapshot(db, float(10000 + i * 100))
    snapshots = await queries.get_portfolio_snapshots(db, limit=3)
    assert len(snapshots) == 3
    # Should return the first 3 (oldest)
    assert snapshots[0]["total_value"] == 10000.0


# --- Chat messages ---


async def test_get_messages_empty(db):
    messages = await queries.get_chat_messages(db)
    assert messages == []


async def test_save_and_get_user_message(db):
    await queries.save_chat_message(db, "user", "Hello!")
    messages = await queries.get_chat_messages(db)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello!"
    assert messages[0]["actions"] is None


async def test_save_message_with_actions(db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    await queries.save_chat_message(
        db, "assistant", "Bought AAPL for you.", actions
    )
    messages = await queries.get_chat_messages(db)
    assert len(messages) == 1
    stored_actions = json.loads(messages[0]["actions"])
    assert stored_actions == actions


async def test_save_message_without_actions_stores_null(db):
    await queries.save_chat_message(db, "user", "Just chatting")
    messages = await queries.get_chat_messages(db)
    assert messages[0]["actions"] is None


async def test_messages_ordered_asc_by_created_at(db):
    await queries.save_chat_message(db, "user", "First message")
    await queries.save_chat_message(db, "assistant", "Second message")
    await queries.save_chat_message(db, "user", "Third message")
    messages = await queries.get_chat_messages(db)
    assert messages[0]["content"] == "First message"
    assert messages[1]["content"] == "Second message"
    assert messages[2]["content"] == "Third message"


async def test_messages_limit(db):
    for i in range(10):
        await queries.save_chat_message(db, "user", f"Message {i}")
    messages = await queries.get_chat_messages(db, limit=5)
    assert len(messages) == 5
