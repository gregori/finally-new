import pytest
from app.llm.schemas import LLMResponse, TradeAction, WatchlistChange
from pydantic import ValidationError


class TestTradeAction:
    def test_valid_buy(self):
        t = TradeAction(ticker="AAPL", side="buy", quantity=10.0)
        assert t.ticker == "AAPL"
        assert t.side == "buy"
        assert t.quantity == 10.0

    def test_valid_sell(self):
        t = TradeAction(ticker="TSLA", side="sell", quantity=5.5)
        assert t.side == "sell"

    def test_invalid_side(self):
        with pytest.raises(ValidationError):
            TradeAction(ticker="AAPL", side="hold", quantity=1.0)

    def test_fractional_quantity(self):
        t = TradeAction(ticker="GOOGL", side="buy", quantity=0.5)
        assert t.quantity == 0.5


class TestWatchlistChange:
    def test_add_action(self):
        w = WatchlistChange(ticker="NVDA", action="add")
        assert w.ticker == "NVDA"
        assert w.action == "add"

    def test_remove_action(self):
        w = WatchlistChange(ticker="META", action="remove")
        assert w.action == "remove"

    def test_invalid_action(self):
        with pytest.raises(ValidationError):
            WatchlistChange(ticker="AAPL", action="toggle")


class TestLLMResponse:
    def test_message_only(self):
        r = LLMResponse(message="Hello")
        assert r.message == "Hello"
        assert r.trades == []
        assert r.watchlist_changes == []

    def test_defaults_are_empty_lists(self):
        r = LLMResponse(message="test")
        assert isinstance(r.trades, list)
        assert isinstance(r.watchlist_changes, list)

    def test_with_trades(self):
        r = LLMResponse(
            message="Buying AAPL",
            trades=[{"ticker": "AAPL", "side": "buy", "quantity": 10}],
        )
        assert len(r.trades) == 1
        assert isinstance(r.trades[0], TradeAction)

    def test_with_watchlist_changes(self):
        r = LLMResponse(
            message="Adding PYPL",
            watchlist_changes=[{"ticker": "PYPL", "action": "add"}],
        )
        assert len(r.watchlist_changes) == 1
        assert isinstance(r.watchlist_changes[0], WatchlistChange)

    def test_full_response(self):
        r = LLMResponse(
            message="Executing trades",
            trades=[
                {"ticker": "AAPL", "side": "buy", "quantity": 5},
                {"ticker": "TSLA", "side": "sell", "quantity": 2},
            ],
            watchlist_changes=[{"ticker": "NVDA", "action": "add"}],
        )
        assert len(r.trades) == 2
        assert len(r.watchlist_changes) == 1

    def test_model_validate_json(self):
        json_str = '{"message": "ok", "trades": [], "watchlist_changes": []}'
        r = LLMResponse.model_validate_json(json_str)
        assert r.message == "ok"

    def test_missing_message_raises(self):
        with pytest.raises(ValidationError):
            LLMResponse(trades=[])
