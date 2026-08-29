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
        # OpenAI 流式响应最后返回真实 token usage。
        # 暂时只对 OpenAI 开启，避免影响其他兼容供应商。
        usage_supported_providers = {
            "openai",
            "deepseek",
            "moonshot",
            "dashscope",
            "xai",
            "volcengine",
            "gemini",
            "zhipu",
        }

        if self.config.provider in usage_supported_providers:
            request_params["stream_options"] = {
                "include_usage": True
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
        max_tokens: int = 21000,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """
        稳定流式输出：

        1. 首次请求在未输出任何文字前失败：
        自动重试。

        2. 已经输出部分文字后发生断流：
        不丢弃已有内容，自动发起“继续回答”请求。

        3. finish_reason == "length"：
        自动继续完成剩余回答。

        4. 续写时自动过滤模型可能重复输出的上一段尾部，
        尽量避免用户看到重复内容。

        5. 最多进行有限次数续写，避免无限循环。
        """

        self.last_usage = None

        # --------------------------------------------------
        # 基础设置
        # --------------------------------------------------
        max_initial_attempts = 3

        # 初始回答之后，最多允许再续写 2 次。
        # 即：初始请求 + 最多 2 段续写。
        max_continuations = 2

        initial_attempt = 0
        continuation_count = 0

        # 已经真正发送给前端的完整回答。
        full_answer = ""

        # 当前请求使用的 messages。
        current_messages = list(messages)

        # 是否已经进入续写模式。
        continuation_mode = False

        last_error: Exception | None = None

        # 累计多个请求的 usage。
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        # --------------------------------------------------
        # 去除续写开头可能出现的重复内容
        # --------------------------------------------------
        def remove_resume_overlap(
            previous_text: str,
            new_text: str,
        ) -> str:
            """
            如果续写模型把上一段结尾重复了一遍，
            删除重复部分。

            最多比较上一段最后 800 个字符。
            """

            if not previous_text or not new_text:
                return new_text

            previous_tail = previous_text[-800:]

            max_overlap = min(
                len(previous_tail),
                len(new_text),
            )

            # 从最长重合开始检查。
            for size in range(
                max_overlap,
                19,
                -1,
            ):
                if (
                    previous_tail[-size:]
                    == new_text[:size]
                ):
                    return new_text[size:]

            return new_text

        # --------------------------------------------------
        # 主循环
        # --------------------------------------------------
        while True:

            emitted_this_request = False
            completed_normally = False
            finish_reason = None

            # 续写请求为了做去重，
            # 暂存开头的一小段文字后再发送给前端。
            resume_buffer = ""

            try:
                stream = self._create_stream(
                    messages=current_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                for chunk in stream:

                    # --------------------------------------
                    # usage
                    # --------------------------------------
                    usage = getattr(
                        chunk,
                        "usage",
                        None,
                    )

                    if usage is not None:
                        request_input = int(
                            getattr(
                                usage,
                                "prompt_tokens",
                                0,
                            )
                            or 0
                        )

                        request_output = int(
                            getattr(
                                usage,
                                "completion_tokens",
                                0,
                            )
                            or 0
                        )

                        request_total = int(
                            getattr(
                                usage,
                                "total_tokens",
                                0,
                            )
                            or 0
                        )

                        total_input_tokens += request_input
                        total_output_tokens += request_output
                        total_tokens += request_total

                        self.last_usage = {
                            "input_tokens": total_input_tokens,
                            "output_tokens": total_output_tokens,
                            "total_tokens": total_tokens,
                        }

                    # usage-only chunk
                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]

                    # --------------------------------------
                    # finish reason
                    # --------------------------------------
                    if choice.finish_reason is not None:
                        finish_reason = choice.finish_reason
                        completed_normally = True

                        print(
                            "STREAM FINISH: "
                            f"model={self.config.name}, "
                            f"reason={finish_reason}"
                        )

                    # --------------------------------------
                    # 不把 reasoning_content 发给前端
                    # --------------------------------------
                    reasoning_text = getattr(
                        choice.delta,
                        "reasoning_content",
                        None,
                    )

                    if reasoning_text:
                        continue

                    text = getattr(
                        choice.delta,
                        "content",
                        None,
                    )

                    if not text:
                        continue

                    emitted_this_request = True

                    # --------------------------------------
                    # 正常首次回答
                    # --------------------------------------
                    if not continuation_mode:
                        full_answer += text
                        yield text
                        continue

                    # --------------------------------------
                    # 续写回答
                    #
                    # 先缓存开头，避免模型重复上一段结尾。
                    # --------------------------------------
                    resume_buffer += text

                    # 先收集约 300 字符，再进行重合判断。
                    if len(resume_buffer) < 300:
                        continue

                    cleaned = remove_resume_overlap(
                        full_answer,
                        resume_buffer,
                    )

                    if cleaned:
                        full_answer += cleaned
                        yield cleaned

                    resume_buffer = ""

                    # 已经完成首次去重，
                    # 后面的流可以继续正常发送。
                    continuation_mode = False

                # ------------------------------------------
                # stream 正常关闭后，
                # 如果续写 buffer 还没吐出去，处理掉。
                # ------------------------------------------
                if resume_buffer:
                    cleaned = remove_resume_overlap(
                        full_answer,
                        resume_buffer,
                    )

                    if cleaned:
                        full_answer += cleaned
                        yield cleaned

                    resume_buffer = ""

                    continuation_mode = False

                # ------------------------------------------
                # 正常结束
                # ------------------------------------------
                if emitted_this_request and completed_normally:

                    # 达到 max_tokens，不认为回答真正完成。
                    if finish_reason == "length":

                        if continuation_count >= max_continuations:
                            print(
                                "⚠️ 已达到最大自动续写次数："
                                f"model={self.config.name}"
                            )
                            return

                        continuation_count += 1

                        print(
                            "↪️ 输出达到长度限制，自动续写："
                            f"model={self.config.name}, "
                            f"continuation="
                            f"{continuation_count}/"
                            f"{max_continuations}"
                        )

                        current_messages = (
                            list(messages)
                            + [
                                {
                                    "role": "assistant",
                                    "content": full_answer,
                                },
                                {
                                    "role": "user",
                                    "content": (
                                        "Continue exactly from where "
                                        "your previous answer stopped. "
                                        "Do not repeat any content "
                                        "already written. "
                                        "Do not restart the answer. "
                                        "Continue only the unfinished "
                                        "part."
                                    ),
                                },
                            ]
                        )

                        continuation_mode = True
                        continue

                    # stop / 正常 finish_reason
                    return

                # ------------------------------------------
                # 已经输出内容，但 provider 没有 finish_reason
                # 视为异常断流，自动续写。
                # ------------------------------------------
                if emitted_this_request:

                    if continuation_count >= max_continuations:
                        print(
                            "⚠️ 流式输出异常结束，"
                            "且已达到最大续写次数："
                            f"model={self.config.name}"
                        )
                        return

                    continuation_count += 1

                    print(
                        "↪️ STREAM INTERRUPTED，"
                        "自动从已有回答继续："
                        f"model={self.config.name}, "
                        f"continuation="
                        f"{continuation_count}/"
                        f"{max_continuations}"
                    )

                    current_messages = (
                        list(messages)
                        + [
                            {
                                "role": "assistant",
                                "content": full_answer,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Your previous response was "
                                    "interrupted. Continue exactly "
                                    "from where it stopped. "
                                    "Do not repeat anything already "
                                    "written and do not restart "
                                    "the answer."
                                ),
                            },
                        ]
                    )

                    continuation_mode = True
                    continue

                # ------------------------------------------
                # 完全空响应
                # ------------------------------------------
                last_error = EmptyProviderResponseError(
                    f"{self.config.name} "
                    "returned an empty response."
                )

                # DeepSeek 空响应继续保留原来的特殊逻辑。
                if self.config.provider == "deepseek":
                    break

            except Exception as error:

                last_error = error

                # ------------------------------------------
                # 已经有完整的部分回答：
                # 不再直接 raise，而是自动续写。
                # ------------------------------------------
                if full_answer:

                    print(
                        "⚠️ STREAM INTERRUPTED AFTER "
                        "PARTIAL OUTPUT: "
                        f"model={self.config.name}, "
                        f"error={repr(error)}"
                    )

                    if continuation_count >= max_continuations:
                        print(
                            "⚠️ 已达到最大自动续写次数，"
                            "保留当前已生成内容。"
                        )
                        return

                    continuation_count += 1

                    current_messages = (
                        list(messages)
                        + [
                            {
                                "role": "assistant",
                                "content": full_answer,
                            },
                            {
                                "role": "user",
                                "content": (
                                    "Your previous response was "
                                    "interrupted unexpectedly. "
                                    "Continue exactly from the next "
                                    "unfinished part. "
                                    "Do not repeat previous text. "
                                    "Do not restart the answer."
                                ),
                            },
                        ]
                    )

                    continuation_mode = True

                    # 断流后稍等一下再重新连接。
                    time.sleep(0.8)

                    continue

                # ------------------------------------------
                # 一个字都没有输出：
                # 使用原来的请求重试机制。
                # ------------------------------------------
                initial_attempt += 1

                if initial_attempt >= max_initial_attempts:
                    break

                wait_seconds = 0.6 * initial_attempt

                print(
                    "Provider request failed before "
                    "producing text; retrying: "
                    f"model={self.config.name}, "
                    f"attempt={initial_attempt}/"
                    f"{max_initial_attempts}, "
                    f"wait={wait_seconds:.1f}s, "
                    f"error={repr(last_error)}"
                )

                time.sleep(wait_seconds)

        raise RuntimeError(
            f"{self.config.name} failed before "
            f"returning any text: {last_error}"
        ) from last_error