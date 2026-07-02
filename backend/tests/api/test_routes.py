"""API route tests for FinAlly backend."""

import pytest

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


async def test_get_watchlist(client):
    r = await client.get("/api/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    tickers = [item["ticker"] for item in body["data"]["watchlist"]]
    assert "AAPL" in tickers
    assert len(tickers) == 10


async def test_add_ticker_valid(client):
    r = await client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    tickers = [item["ticker"] for item in body["data"]["watchlist"]]
    assert "PYPL" in tickers


async def test_add_ticker_invalid(client):
    r = await client.post("/api/watchlist", json={"ticker": "INVALID123"})
    assert r.status_code == 400
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "UNKNOWN_TICKER"


async def test_add_ticker_duplicate(client):
    # AAPL is in the default watchlist seed data
    r = await client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 409
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "DUPLICATE_TICKER"


async def test_remove_ticker(client):
    r = await client.delete("/api/watchlist/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True

    # Confirm it is gone
    r2 = await client.get("/api/watchlist")
    tickers = [item["ticker"] for item in r2.json()["data"]["watchlist"]]
    assert "AAPL" not in tickers


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


async def test_get_portfolio_empty(client):
    r = await client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["cash"] == pytest.approx(10000.0)
    assert data["positions"] == []
    assert data["total_value"] == pytest.approx(10000.0)


async def test_get_portfolio_history_empty(client):
    r = await client.get("/api/portfolio/history")
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["snapshots"] == []


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------


async def test_buy_success(client_with_prices):
    r = await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert data["ticker"] == "AAPL"
    assert data["side"] == "buy"
    assert data["quantity"] == 1
    assert data["price"] > 0
    assert data["new_cash"] < 10000.0


async def test_buy_updates_portfolio(client_with_prices):
    await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 2},
    )
    r = await client_with_prices.get("/api/portfolio")
    data = r.json()["data"]
    tickers = [p["ticker"] for p in data["positions"]]
    assert "AAPL" in tickers
    pos = next(p for p in data["positions"] if p["ticker"] == "AAPL")
    assert pos["quantity"] == pytest.approx(2.0)


async def test_buy_insufficient_cash(client_with_prices):
    # Attempt to buy more shares than cash allows (NVDA is ~$875 each)
    r = await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "NVDA", "side": "buy", "quantity": 100},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "INSUFFICIENT_CASH"


async def test_sell_insufficient_shares(client_with_prices):
    r = await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "sell", "quantity": 5},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "INSUFFICIENT_SHARES"


async def test_sell_success(client_with_prices):
    # First buy, then sell
    await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "buy", "quantity": 2},
    )
    r = await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "MSFT", "side": "sell", "quantity": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"]["side"] == "sell"


async def test_trade_history_after_buy(client_with_prices):
    await client_with_prices.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "side": "buy", "quantity": 1},
    )
    r = await client_with_prices.get("/api/portfolio/history")
    assert r.status_code == 200
    snapshots = r.json()["data"]["snapshots"]
    assert len(snapshots) >= 1
    assert snapshots[0]["total_value"] > 0


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


async def test_chat_mock_response(client):
    r = await client.post(
        "/api/chat", json={"message": "How is my portfolio?"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    data = body["data"]
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0
    assert isinstance(data["trades_executed"], list)
    assert isinstance(data["watchlist_changes"], list)


async def test_chat_empty_message(client):
    r = await client.post("/api/chat", json={"message": "  "})
    assert r.status_code == 400
    body = r.json()
    assert body["success"] is False
    assert body["code"] == "EMPTY_MESSAGE"
