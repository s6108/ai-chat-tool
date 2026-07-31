from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from services.model_config import get_model_config


class MissingModelApiKeyError(RuntimeError):
    """Raised when the selected model has no configured API key."""


def prepare_messages(
    model_name: str,
    messages: list[dict[str, Any]],
    *,
    history_limit: int = 12,
) -> list[dict[str, Any]]:
    """Return recent messages in a format supported by the selected model."""
    config = get_model_config(model_name)
    recent_messages = messages[-history_limit:]

    if config.supports_vision:
        return recent_messages

    return [
        message
        for message in recent_messages
        if isinstance(message.get("content"), str)
    ]


def stream_model_response(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    max_tokens: int = 1200,
    temperature: float = 0.7,
) -> Iterator[str]:
    """Stream text from any currently configured OpenAI-compatible provider."""
    config = get_model_config(model_name)

    if not config.api_key:
        raise MissingModelApiKeyError(model_name)

    client = OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=45.0,
        max_retries=1,
    )

    request_params: dict[str, Any] = {
        "model": config.model_id,
        "messages": messages,
        "stream": True,
    }

    if config.uses_max_completion_tokens:
        request_params["max_completion_tokens"] = max_tokens
    else:
        request_params["max_tokens"] = max_tokens
        request_params["temperature"] = temperature

    stream = client.chat.completions.create(**request_params)

    for chunk in stream:
        if not chunk.choices:
            continue

        text = chunk.choices[0].delta.content
        if text:
            yield text
