from app.llm.prompt import build_portfolio_context, build_system_prompt


class TestBuildSystemPrompt:
    def test_returns_non_empty_string(self):
        prompt = build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_finally(self):
        prompt = build_system_prompt()
        assert "FinAlly" in prompt

    def test_mentions_json(self):
        prompt = build_system_prompt()
        assert "JSON" in prompt or "json" in prompt

    def test_mentions_trades(self):
        prompt = build_system_prompt()
        assert "trade" in prompt.lower()


class TestBuildPortfolioContext:
    def _make_portfolio(self, cash=5000.0, total_value=7500.0, positions=None):
        return {
            "cash": cash,
            "total_value": total_value,
            "positions": positions or [],
        }

    def test_returns_string(self):
        ctx = build_portfolio_context(self._make_portfolio())
        assert isinstance(ctx, str)

    def test_includes_cash(self):
        ctx = build_portfolio_context(self._make_portfolio(cash=1234.56))
        assert "1,234.56" in ctx

    def test_includes_total_value(self):
        ctx = build_portfolio_context(
            self._make_portfolio(total_value=9999.00)
        )
        assert "9,999.00" in ctx

    def test_no_positions_message(self):
        ctx = build_portfolio_context(self._make_portfolio(positions=[]))
        assert "none" in ctx.lower()

    def test_with_positions(self):
        positions = [
            {
                "ticker": "AAPL",
                "quantity": 10.0,
                "avg_cost": 150.0,
                "current_price": 175.0,
                "unrealized_pnl": 250.0,
                "pnl_pct": 16.67,
            }
        ]
        ctx = build_portfolio_context(
            self._make_portfolio(positions=positions)
        )
        assert "AAPL" in ctx
        assert "10" in ctx
        assert "150.00" in ctx
        assert "175.00" in ctx
        assert "250.00" in ctx

    def test_positive_pnl_has_plus_sign(self):
        positions = [
            {
                "ticker": "MSFT",
                "quantity": 5.0,
                "avg_cost": 300.0,
                "current_price": 350.0,
                "unrealized_pnl": 250.0,
                "pnl_pct": 16.67,
            }
        ]
        ctx = build_portfolio_context(
            self._make_portfolio(positions=positions)
        )
        assert "+$250.00" in ctx

    def test_negative_pnl_no_plus_sign(self):
        positions = [
            {
                "ticker": "NFLX",
                "quantity": 3.0,
                "avg_cost": 500.0,
                "current_price": 400.0,
                "unrealized_pnl": -300.0,
                "pnl_pct": -20.0,
            }
        ]
        ctx = build_portfolio_context(
            self._make_portfolio(positions=positions)
        )
        assert "-$300.00" in ctx

    def test_multiple_positions(self):
        positions = [
            {
                "ticker": "AAPL",
                "quantity": 10,
                "avg_cost": 150,
                "current_price": 175,
                "unrealized_pnl": 250,
                "pnl_pct": 16.67,
            },
            {
                "ticker": "GOOGL",
                "quantity": 2,
                "avg_cost": 170,
                "current_price": 160,
                "unrealized_pnl": -20,
                "pnl_pct": -5.88,
            },
        ]
        ctx = build_portfolio_context(
            self._make_portfolio(positions=positions)
        )
        assert "AAPL" in ctx
        assert "GOOGL" in ctx
