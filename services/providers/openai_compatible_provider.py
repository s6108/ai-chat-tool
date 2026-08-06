from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import OpenAI

from services.providers.base_provider import BaseProvider


class EmptyProviderResponseError(RuntimeError):
    """Raised when a provider finishes without returning any text."""


class OpenAICompatibleProvider(BaseProvider):
    """Provider for APIs compatible with OpenAI chat completions."""

    def _create_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
    ) -> Any:
        client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=45.0,
            # SDK-level retry handles transient connection and 5xx failures.
            max_retries=1,
        )

        request_params: dict[str, Any] = {
            "model": self.config.model_id,
            "messages": messages,
            "stream": True,
        }
        

        if self.config.uses_max_completion_tokens:
            request_params["max_completion_tokens"] = max_tokens
        else:
            request_params["max_tokens"] = max_tokens

            if self.config.provider == "moonshot":
                request_params["temperature"] = 1
            else:
                request_params["temperature"] = temperature

        return client.chat.completions.create(**request_params)

    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """
        Stream provider text.

        A request is retried once only when it fails before producing any text,
        or when the provider closes the stream with an entirely empty answer.
        A partially emitted answer is never retried, preventing duplicated text.
        """
        last_error: Exception | None = None

        for attempt in range(1, 3):
            emitted_text = False

            try:
                stream = self._create_stream(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                for chunk in stream:
                    if not chunk.choices:
                        continue

                    text = chunk.choices[0].delta.content
                    if not text:
                        continue

                    emitted_text = True
                    yield text

                if emitted_text:
                    return

                last_error = EmptyProviderResponseError(
                    f"{self.config.name} returned an empty response."
                )

            except Exception as error:
                # Never retry after text has already reached the user, because
                # restarting would duplicate the beginning of the answer.
                if emitted_text:
                    raise

                last_error = error

            if attempt == 1:
                print(
                    "Provider request returned no text before completion; "
                    f"retrying once: model={self.config.name}, "
                    f"error={last_error}"
                )

        raise RuntimeError(
            f"{self.config.name} failed before returning any text: "
            f"{last_error}"
        ) from last_error
