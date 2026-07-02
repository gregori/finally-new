import asyncio
import os

import litellm

from .prompt import build_portfolio_context, build_system_prompt
from .schemas import LLMResponse

MODEL = "openai/deepseek-v4-flash-free"
API_BASE = "https://opencode.ai/zen/v1"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}

litellm.drop_params = True

_MOCK_RESPONSE = LLMResponse(
    message=(
        "I've analyzed your portfolio and it looks well-diversified. "
        "Let me know if you'd like to make any trades."
    ),
    trades=[],
    watchlist_changes=[],
)


async def chat(
    user_message: str,
    history: list[dict],
    portfolio: dict,
) -> LLMResponse:
    """
    Send a message and return a structured LLM response.

    Args:
        user_message: The user's latest message.
        history: Prior conversation turns as
            [{"role": "user"|"assistant", "content": str}].
        portfolio: Current portfolio state dict.

    Returns:
        Parsed LLMResponse with message, trades, and watchlist changes.

    Raises:
        ValueError: If the LLM call fails after 2 retries.

    """
    if os.getenv("LLM_MOCK", "false").lower() == "true":
        return _MOCK_RESPONSE

    api_key = os.environ["OPENCODE_API_KEY"]

    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": build_portfolio_context(portfolio)},
        *history,
        {"role": "user", "content": user_message},
    ]

    last_exc: Exception | None = None
    for _ in range(3):
        try:
            response = await asyncio.to_thread(
                litellm.completion,
                model=MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                extra_body=EXTRA_BODY,
                api_base=API_BASE,
                api_key=api_key,
                timeout=30,
            )
            content = response.choices[0].message.content
            return LLMResponse.model_validate_json(content)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc

    msg = "FinAlly is temporarily unavailable. Please try again in a moment."
    raise ValueError(msg) from last_exc
