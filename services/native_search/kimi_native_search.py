from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class KimiNativeSearch(BaseNativeSearch):
    """
    Kimi 原生 Web Search Adapter。

    使用 Moonshot/Kimi 内置的 $web_search 工具。

    搜索本身由 Kimi 执行。
    Megor 只负责：
    1. 声明 $web_search
    2. 接收 tool_calls
    3. 将 arguments 原样作为 tool result 回传
    4. 获取最终回答

    原生搜索失败时，由 Megor 上层进入 Tavily Safety Net。
    """

    model_name = "Kimi"
    provider = "moonshot"

    def __init__(self) -> None:
        self.config = get_model_config("Kimi")

        if not self.config.api_key:
            raise RuntimeError(
                "Kimi API key is missing."
            )

        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=90.0,
            max_retries=1,
        )

    # ==================================================
    # 从 Kimi 搜索 arguments 中尽量提取可见来源
    # ==================================================
    def _extract_sources(
        self,
        value: Any,
        *,
        results: list[NativeSearchResult],
        seen_urls: set[str],
    ) -> None:

        if isinstance(value, dict):
            url = (
                value.get("url")
                or value.get("uri")
                or value.get("link")
                or ""
            )

            if isinstance(url, str):
                url = url.strip()

                if url.startswith(
                    ("http://", "https://")
                ):
                    normalized_url = (
                        url
                        .rstrip("/")
                        .casefold()
                    )

                    if normalized_url not in seen_urls:
                        seen_urls.add(normalized_url)

                        title = (
                            value.get("title")
                            or value.get("name")
                            or value.get("site_name")
                            or ""
                        )

                        if not isinstance(title, str):
                            title = ""

                        results.append(
                            NativeSearchResult(
                                title=title.strip(),
                                url=url,
                                source="Kimi Web Search",
                            )
                        )

            for nested_value in value.values():
                self._extract_sources(
                    nested_value,
                    results=results,
                    seen_urls=seen_urls,
                )

            return

        if isinstance(value, list):
            for item in value:
                self._extract_sources(
                    item,
                    results=results,
                    seen_urls=seen_urls,
                )

            return

        # 某些返回内容可能把 URL 放在字符串中
        if isinstance(value, str):
            urls = re.findall(
                r"https?://[^\s<>\]\"')]+",
                value,
            )

            for url in urls:
                url = url.rstrip(
                    ".,;:"
                )

                normalized_url = (
                    url
                    .rstrip("/")
                    .casefold()
                )

                if normalized_url in seen_urls:
                    continue

                seen_urls.add(normalized_url)

                results.append(
                    NativeSearchResult(
                        title="",
                        url=url,
                        source="Kimi Web Search",
                    )
                )

    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
    ) -> NativeSearchResponse:

        query = (query or "").strip()

        if not query:
            return NativeSearchResponse(
                success=False,
                model_name=self.model_name,
                provider=self.provider,
                query="",
                error="Empty search query.",
                should_fallback=True,
            )

        try:
            kimi_messages: list[dict[str, Any]] = []

            # ==================================================
            # 唯一 system message
            # ==================================================
            kimi_messages.append(
                {
                    "role": "system",
                    "content": (
                        "You are Kimi performing live web research "
                        "for the current user request. "
                        "Use the built-in $web_search tool before "
                        "answering. Prefer current, reliable, primary "
                        "and authoritative sources when available. "
                        "Do not rely on stale internal knowledge for "
                        "time-sensitive facts. "
                        "Conversation history may contain statements "
                        "from different AI models. Treat those statements "
                        "as context, not verified facts. "
                        "If claims conflict, independently verify them "
                        "with web search before reaching a conclusion."
                    ),
                }
            )

            # ==================================================
            # 最近圆桌 / 对话上下文
            # 只保留 user + assistant，避免多个 system
            # ==================================================
            if messages:
                for message in messages[-8:]:
                    role = message.get("role")
                    content = message.get("content")

                    if role not in {
                        "user",
                        "assistant",
                    }:
                        continue

                    if not isinstance(content, str):
                        continue

                    content = content.strip()

                    if not content:
                        continue

                    if len(content) > 1500:
                        content = content[:1500]

                    kimi_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            # ==================================================
            # 当前搜索问题
            # ==================================================
            kimi_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            tools = [
                {
                    "type": "builtin_function",
                    "function": {
                        "name": "$web_search",
                    },
                }
            ]

            used_web_search = False

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            final_answer = ""

            # 防止异常情况下无限 tool loop
            max_rounds = 6

            for round_index in range(
                1,
                max_rounds + 1,
            ):
                completion = (
                    self.client.chat.completions.create(
                        model=self.config.model_id,
                        messages=kimi_messages,
                        tools=tools,
                        max_tokens=2400,
                        temperature=1,
                    )
                )

                if not completion.choices:
                    raise RuntimeError(
                        "Kimi returned no choices."
                    )

                choice = completion.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason

                # ==================================================
                # TEMP DIAGNOSTIC: inspect the REAL Kimi response
                # Read-only: does not change search / fallback behavior.
                # ==================================================
                try:
                    print(
                        f"\n🧪 [KIMI RAW] round={round_index} "
                        f"completion_type={type(completion).__name__}"
                    )
                    print(
                        "🧪 [KIMI RAW] finish_reason =",
                        finish_reason,
                    )

                    if hasattr(completion, "model_dump"):
                        raw_completion = completion.model_dump()
                        print(
                            "🧪 [KIMI RAW] top_keys =",
                            list(raw_completion.keys()),
                        )
                    else:
                        raw_completion = None

                    print(
                        "🧪 [KIMI RAW] message_type =",
                        type(message).__name__,
                    )
                    print(
                        "🧪 [KIMI RAW] message.content_type =",
                        type(message.content).__name__,
                    )
                    print(
                        "🧪 [KIMI RAW] message.content_preview =",
                        repr(
                            (message.content or "")[:500]
                            if isinstance(message.content, str)
                            else message.content
                        ),
                    )

                    raw_tool_calls = message.tool_calls or []
                    print(
                        "🧪 [KIMI RAW] tool_calls_count =",
                        len(raw_tool_calls),
                    )

                    for idx, tool_call in enumerate(raw_tool_calls):
                        function = getattr(tool_call, "function", None)
                        tool_type = getattr(tool_call, "type", None)
                        tool_id = getattr(tool_call, "id", None)
                        function_name = (
                            getattr(function, "name", None)
                            if function is not None
                            else None
                        )
                        function_arguments = (
                            getattr(function, "arguments", None)
                            if function is not None
                            else None
                        )

                        print(
                            f"🧪 [KIMI RAW] tool_call[{idx}].id =",
                            tool_id,
                        )
                        print(
                            f"🧪 [KIMI RAW] tool_call[{idx}].type =",
                            tool_type,
                        )
                        print(
                            f"🧪 [KIMI RAW] tool_call[{idx}].function.name =",
                            function_name,
                        )
                        print(
                            f"🧪 [KIMI RAW] tool_call[{idx}].arguments_type =",
                            type(function_arguments).__name__,
                        )

                        if isinstance(function_arguments, str):
                            print(
                                f"🧪 [KIMI RAW] tool_call[{idx}].arguments_len =",
                                len(function_arguments),
                            )
                            print(
                                f"🧪 [KIMI RAW] tool_call[{idx}].arguments_preview =",
                                repr(function_arguments[:2000]),
                            )

                            try:
                                parsed_arguments = json.loads(
                                    function_arguments
                                )
                                print(
                                    f"🧪 [KIMI RAW] tool_call[{idx}].arguments_json_type =",
                                    type(parsed_arguments).__name__,
                                )

                                if isinstance(parsed_arguments, dict):
                                    print(
                                        f"🧪 [KIMI RAW] tool_call[{idx}].arguments_top_keys =",
                                        list(parsed_arguments.keys()),
                                    )

                                    for key in (
                                        "results",
                                        "sources",
                                        "data",
                                        "items",
                                        "documents",
                                        "web_results",
                                        "search_results",
                                        "references",
                                        "usage",
                                    ):
                                        if key not in parsed_arguments:
                                            continue
                                        value = parsed_arguments.get(key)
                                        if isinstance(value, list):
                                            print(
                                                f"🧪 [KIMI RAW] tool_call[{idx}].{key}_count =",
                                                len(value),
                                            )
                                            if value:
                                                first = value[0]
                                                if isinstance(first, dict):
                                                    print(
                                                        f"🧪 [KIMI RAW] tool_call[{idx}].{key}[0].keys =",
                                                        list(first.keys()),
                                                    )
                                                else:
                                                    print(
                                                        f"🧪 [KIMI RAW] tool_call[{idx}].{key}[0]_type =",
                                                        type(first).__name__,
                                                    )
                                        elif isinstance(value, dict):
                                            print(
                                                f"🧪 [KIMI RAW] tool_call[{idx}].{key}.keys =",
                                                list(value.keys()),
                                            )
                                        else:
                                            print(
                                                f"🧪 [KIMI RAW] tool_call[{idx}].{key} =",
                                                value,
                                            )

                            except Exception as parse_error:
                                print(
                                    f"⚠️ [KIMI RAW] tool_call[{idx}] arguments JSON parse failed:",
                                    repr(parse_error),
                                )

                    if raw_completion is not None:
                        usage = raw_completion.get("usage")
                        if isinstance(usage, dict):
                            print(
                                "🧪 [KIMI RAW] usage.keys =",
                                list(usage.keys()),
                            )
                        elif usage is not None:
                            print(
                                "🧪 [KIMI RAW] usage =",
                                usage,
                            )

                except Exception as diagnostic_error:
                    print(
                        "⚠️ [KIMI RAW] diagnostic failed:",
                        repr(diagnostic_error),
                    )

                # ==================================================
                # Kimi 请求调用 $web_search
                # ==================================================
                if finish_reason == "tool_calls":
                    tool_calls = (
                        message.tool_calls
                        or []
                    )

                    if not tool_calls:
                        raise RuntimeError(
                            "Kimi returned tool_calls finish_reason "
                            "without any tool calls."
                        )

                    # 必须把 assistant 的完整 tool-call message
                    # 放回上下文
                    if hasattr(
                        message,
                        "model_dump",
                    ):
                        assistant_message = (
                            message.model_dump(
                                exclude_none=True
                            )
                        )
                    else:
                        assistant_message = {
                            "role": "assistant",
                            "content": (
                                message.content
                                or ""
                            ),
                            "tool_calls": tool_calls,
                        }

                    kimi_messages.append(
                        assistant_message
                    )

                    for tool_call in tool_calls:
                        tool_name = (
                            tool_call.function.name
                        )

                        raw_arguments = (
                            tool_call.function.arguments
                            or "{}"
                        )

                        try:
                            arguments = json.loads(
                                raw_arguments
                            )
                        except json.JSONDecodeError:
                            arguments = {
                                "raw": raw_arguments
                            }

                        if tool_name == "$web_search":
                            used_web_search = True

                            # Kimi 官方要求：
                            # arguments 原样回传即可，
                            # 不由 Megor 自己执行搜索。
                            tool_result = arguments

                            # 尽可能提取搜索来源，
                            # 仅用于 Megor 的来源展示/记录。
                            self._extract_sources(
                                arguments,
                                results=native_results,
                                seen_urls=seen_urls,
                            )

                            usage = arguments.get(
                                "usage",
                                {}
                            )

                            search_tokens = (
                                usage.get(
                                    "total_tokens"
                                )
                                if isinstance(
                                    usage,
                                    dict,
                                )
                                else None
                            )

                            if search_tokens is not None:
                                print(
                                    "🌐 Kimi search content tokens:",
                                    search_tokens,
                                )

                        else:
                            tool_result = {
                                "error": (
                                    "Unsupported tool: "
                                    f"{tool_name}"
                                )
                            }

                        kimi_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": (
                                    tool_call.id
                                ),
                                "name": tool_name,
                                "content": json.dumps(
                                    tool_result,
                                    ensure_ascii=False,
                                ),
                            }
                        )

                    # Kimi 下一轮会根据搜索结果继续回答
                    continue

                # ==================================================
                # 最终回答
                # ==================================================
                content = (
                    message.content
                    or ""
                )

                if isinstance(content, str):
                    final_answer = (
                        content.strip()
                    )

                break

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 Kimi native search:",
                {
                    "web_search": used_web_search,
                    "sources": len(
                        native_results
                    ),
                },
            )

            # ==================================================
            # 安全判断
            # ==================================================
            if not used_web_search:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    answer=final_answer,
                    results=native_results,
                    error=(
                        "Kimi returned without using "
                        "the native $web_search tool."
                    ),
                    should_fallback=True,
                )

            if not final_answer:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    error=(
                        "Kimi native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ Kimi native search succeeded: "
                f"{len(native_results)} visible sources"
            )

            return NativeSearchResponse(
                success=True,
                model_name=self.model_name,
                provider=self.provider,
                query=query,
                results=native_results,
                answer=final_answer,
                should_fallback=False,
            )

        except Exception as error:
            print(
                "❌ Kimi native search failed:",
                repr(error),
            )

            return NativeSearchResponse(
                success=False,
                model_name=self.model_name,
                provider=self.provider,
                query=query,
                error=str(error),
                should_fallback=True,
            )