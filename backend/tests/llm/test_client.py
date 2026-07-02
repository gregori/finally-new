from unittest.mock import MagicMock, patch

import pytest
from app.llm.client import chat
from app.llm.schemas import LLMResponse

_EMPTY_PORTFOLIO = {"cash": 10000.0, "total_value": 10000.0, "positions": []}


class TestMockMode:
    async def test_mock_mode_returns_llm_response(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await chat("Hello", [], _EMPTY_PORTFOLIO)
        assert isinstance(result, LLMResponse)

    async def test_mock_mode_returns_non_empty_message(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await chat("Hello", [], _EMPTY_PORTFOLIO)
        assert len(result.message) > 0

    async def test_mock_mode_empty_trades(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await chat("Buy AAPL", [], _EMPTY_PORTFOLIO)
        assert result.trades == []

    async def test_mock_mode_empty_watchlist_changes(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "true")
        result = await chat("Add NVDA", [], _EMPTY_PORTFOLIO)
        assert result.watchlist_changes == []

    async def test_mock_mode_case_insensitive_true(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "TRUE")
        result = await chat("Hello", [], _EMPTY_PORTFOLIO)
        assert isinstance(result, LLMResponse)

    async def test_mock_mode_false_does_not_short_circuit(self, monkeypatch):
        """When LLM_MOCK=false, the real call path is taken."""
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
        exc = RuntimeError("no api")
        with (
            patch(
                "app.llm.client.litellm.completion",
                side_effect=exc,
            ),
            pytest.raises(ValueError, match="temporarily unavailable"),
        ):
            await chat("Hello", [], _EMPTY_PORTFOLIO)


class TestRetryBehavior:
    async def test_raises_value_error_after_3_attempts(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
        call_count = 0

        def fail(**_kwargs):
            nonlocal call_count
            call_count += 1
            msg = "timeout"
            raise ConnectionError(msg)

        with (
            patch(
                "app.llm.client.litellm.completion",
                side_effect=fail,
            ),
            pytest.raises(ValueError, match="temporarily unavailable"),
        ):
            await chat("Hello", [], _EMPTY_PORTFOLIO)

        assert call_count == 3

    async def test_succeeds_on_second_attempt(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
        call_count = 0

        valid_json = (
            '{"message": "recovered", "trades": [], "watchlist_changes": []}'
        )
        mock_choice = MagicMock()
        mock_choice.message.content = valid_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        def flaky(**_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                msg = "first attempt fails"
                raise ConnectionError(msg)
            return mock_response

        with patch("app.llm.client.litellm.completion", side_effect=flaky):
            result = await chat("Hello", [], _EMPTY_PORTFOLIO)

        assert result.message == "recovered"
        assert call_count == 2

    async def test_error_message_is_user_friendly(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
        exc = Exception("raw error")
        with (
            patch(
                "app.llm.client.litellm.completion",
                side_effect=exc,
            ),
            pytest.raises(
                ValueError, match="temporarily unavailable"
            ) as exc_info,
        ):
            await chat("Hello", [], _EMPTY_PORTFOLIO)
        assert "raw error" not in str(exc_info.value)


class TestMessageConstruction:
    async def test_passes_history_to_completion(self, monkeypatch):
        monkeypatch.setenv("LLM_MOCK", "false")
        monkeypatch.setenv("OPENCODE_API_KEY", "test-key")

        captured_messages = []
        valid_json = '{"message": "ok", "trades": [], "watchlist_changes": []}'
        mock_choice = MagicMock()
        mock_choice.message.content = valid_json
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        def capture(**kwargs):
            captured_messages.extend(kwargs.get("messages", []))
            return mock_response

        history = [
            {"role": "user", "content": "prior question"},
            {"role": "assistant", "content": "prior answer"},
        ]

        with patch("app.llm.client.litellm.completion", side_effect=capture):
            await chat("new question", history, _EMPTY_PORTFOLIO)

        roles = [m["role"] for m in captured_messages]
        assert roles[0] == "system"
        contents = [m["content"] for m in captured_messages]
        assert any("prior question" in c for c in contents)
        assert any("prior answer" in c for c in contents)
        assert any("new question" in c for c in contents)
