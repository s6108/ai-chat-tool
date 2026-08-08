from __future__ import annotations

from collections.abc import Iterator
from typing import Any
import time

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

        for attempt in range(1, 4):
            emitted_text = False

            try:
                stream = self._create_stream(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                completed_normally = False

                for chunk in stream:
                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]

                    if choice.finish_reason is not None:
                        completed_normally = True

                    text = choice.delta.content
                    if not text:
                        continue

                    emitted_text = True
                    yield text

                if emitted_text:
                    if completed_normally:
                        return

                    raise RuntimeError(
                        f"{self.config.name} stream ended before receiving a finish reason."
                    )

                last_error = EmptyProviderResponseError(
                    f"{self.config.name} returned an empty response."
                )

            except Exception as error:
                # Never retry after text has already reached the user, because
                # restarting would duplicate the beginning of the answer.
                if emitted_text:
                    raise

                last_error = error

            if attempt < 3:
                wait_seconds = 0.6 * attempt

                print(
                    "Provider request returned no text before completion; "
                    f"retrying: model={self.config.name}, "
                    f"attempt={attempt}/3, "
                    f"wait={wait_seconds:.1f}s, "
                    f"error={last_error}"
                )

                time.sleep(wait_seconds)

        raise RuntimeError(
            f"{self.config.name} failed before returning any text: "
            f"{last_error}"
        ) from last_error
