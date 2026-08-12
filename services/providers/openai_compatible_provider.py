from __future__ import annotations

from collections.abc import Iterator
from typing import Any
import time

from openai import OpenAI

from services.providers.base_provider import BaseProvider


class EmptyProviderResponseError(RuntimeError):
    """Raised when a provider finishes without returning any text."""


def _messages_have_image(
    messages: list[dict[str, Any]],
) -> bool:
    """
    判断当前消息中是否包含图片。

    兼容 OpenAI-style multimodal message：

    {
        "role": "user",
        "content": [
            {"type": "text", ...},
            {"type": "image_url", ...},
        ],
    }

    只有配置了 vision_model_id 的品牌才会因此切换模型。
    """

    for message in messages:
        content = message.get("content")

        if not isinstance(content, list):
            continue

        for part in content:
            if not isinstance(part, dict):
                continue

            part_type = (
                part.get("type")
                or ""
            )

            if part_type in {
                "image_url",
                "input_image",
                "image",
            }:
                return True

    return False


class OpenAICompatibleProvider(BaseProvider):
    """
    Provider for APIs compatible with OpenAI chat completions.

    支持同一品牌内部自动切换：
    - 普通文本模型：config.model_id
    - 视觉模型：config.vision_model_id

    用户界面仍然只显示一个品牌名称。
    """

    def _select_model_id(
        self,
        messages: list[dict[str, Any]],
    ) -> str:
        """
        根据消息内容选择当前实际调用的模型。

        如果：
        1. 当前消息包含图片；
        2. 当前品牌配置了 vision_model_id；

        则使用视觉模型。

        否则始终使用默认文本模型。
        """

        has_image = _messages_have_image(
            messages
        )

        vision_model_id = getattr(
            self.config,
            "vision_model_id",
            None,
        )

        if has_image and vision_model_id:
            print("=" * 60)
            print("🚨 ACTUAL PROVIDER MODEL")
            print(f"Brand: {self.config.name}")
            print(f"Has image: {has_image}")
            print(f"Actual model_id: {vision_model_id}")
            print("=" * 60)

            return vision_model_id

        print("=" * 60)
        print("🚨 ACTUAL PROVIDER MODEL")
        print(f"Brand: {self.config.name}")
        print(f"Has image: {has_image}")
        print(f"Actual model_id: {self.config.model_id}")
        print("=" * 60)

        return self.config.model_id

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

            # SDK-level retry handles transient
            # connection and 5xx failures.
            max_retries=1,
        )

        selected_model_id = (
            self._select_model_id(
                messages
            )
        )

        request_params: dict[str, Any] = {
            "model": selected_model_id,
            "messages": messages,
            "stream": True,
        }

        if self.config.uses_max_completion_tokens:
            request_params[
                "max_completion_tokens"
            ] = max_tokens

        else:
            request_params[
                "max_tokens"
            ] = max_tokens

            if self.config.provider == "moonshot":
                request_params[
                    "temperature"
                ] = 1

            else:
                request_params[
                    "temperature"
                ] = temperature

        return client.chat.completions.create(
            **request_params
        )

    def stream_chat(
        self,
        *,
        messages: list[dict[str, Any]],
        max_tokens: int = 1200,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """
        Stream provider text.

        A request is retried only when it fails before
        producing any text, or when the provider closes
        the stream with an entirely empty answer.

        A partially emitted answer is never retried,
        preventing duplicated text.
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

                    if (
                        choice.finish_reason
                        is not None
                    ):
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
                        f"{self.config.name} "
                        "stream ended before receiving "
                        "a finish reason."
                    )

                last_error = (
                    EmptyProviderResponseError(
                        f"{self.config.name} "
                        "returned an empty response."
                    )
                )

            except Exception as error:
                # Never retry after text has already
                # reached the user because restarting
                # would duplicate the beginning.
                if emitted_text:
                    raise

                last_error = error

            if attempt < 3:
                wait_seconds = (
                    0.6 * attempt
                )

                print(
                    "Provider request returned no text "
                    "before completion; retrying: "
                    f"model={self.config.name}, "
                    f"attempt={attempt}/3, "
                    f"wait={wait_seconds:.1f}s, "
                    f"error={last_error}"
                )

                time.sleep(
                    wait_seconds
                )

        raise RuntimeError(
            f"{self.config.name} failed before "
            f"returning any text: {last_error}"
        ) from last_error