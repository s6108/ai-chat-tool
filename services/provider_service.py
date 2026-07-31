from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from services.model_config import get_model_config
from services.providers.provider_factory import ProviderFactory


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
    """Stream text through the provider adapter selected for the model."""
    config = get_model_config(model_name)

    if not config.api_key:
        raise MissingModelApiKeyError(model_name)

    provider = ProviderFactory.create(config)

    yield from provider.stream_chat(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
