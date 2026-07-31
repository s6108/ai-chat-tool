from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from anthropic import Anthropic

from services.model_config import ModelConfig
from services.providers.base_provider import BaseProvider


class ClaudeProvider(BaseProvider):
    """Claude adapter using Anthropic's native Messages API."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = Anthropic(
            api_key=config.api_key,
            timeout=60.0,
            max_retries=1,
        )

    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        # Claude Sonnet 5 不接受非默认 temperature。
        del temperature

        system_parts: list[str] = []
        claude_messages: list[dict[str, str]] = []

        for message in messages:
            role = message.get("role")
            content = message.get("content", "")

            if not isinstance(content, str):
                continue

            if role == "system":
                if content.strip():
                    system_parts.append(content)
                continue

            if role in {"user", "assistant"}:
                claude_messages.append(
                    {
                        "role": role,
                        "content": content,
                    }
                )

        if not claude_messages:
            raise ValueError("Claude received no valid text messages.")

        request_args: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": claude_messages,
            "max_tokens": max_tokens,
        }

        if system_parts:
            request_args["system"] = "\n\n".join(system_parts)

        yielded_text = False

        with self.client.messages.stream(**request_args) as stream:
            for text in stream.text_stream:
                if text:
                    yielded_text = True
                    yield text

        if not yielded_text:
            raise RuntimeError("Claude returned an empty response.")