from __future__ import annotations

from typing import Any

import anthropic

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class ClaudeNativeSearch(BaseNativeSearch):
    """
    Claude 原生 Web Search Adapter。

    使用 Anthropic Messages API + Web Search server tool。

    本文件只负责 Claude 自己的原生搜索。
    如果失败，由 Megor 上层进入 Tavily Safety Net。
    """

    model_name = "Claude"
    provider = "anthropic"

    def __init__(self) -> None:
        self.config = get_model_config("Claude")

        if not self.config.api_key:
            raise RuntimeError(
                "Claude API key is missing."
            )

        self.client = anthropic.Anthropic(
            api_key=self.config.api_key,
        )

    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        search_mode: str = "research",
        allow_no_search: bool = False,
    ):
        """
        Claude Messages API + Web Search server tool, true streaming.

        yield:
            ("delta", text)
            ("complete", NativeSearchResponse)

        allow_no_search=True is used by Claude unified mode:
        Claude may answer stable knowledge directly without calling web search.
        """

        query = (query or "").strip()

        if not query:
            yield (
                "complete",
                NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query="",
                    error="Empty search query.",
                    should_fallback=True,
                ),
            )
            return

        try:
            is_fast_search = (
                search_mode == "fast"
            )

            # Keep the fast path deliberately small.
            max_tokens = (
                700
                if is_fast_search
                else 1400
            )

            max_uses = (
                2
                if is_fast_search
                else 5
            )

            if is_fast_search:
                search_instruction = (
                    "Answer the user's request directly and concisely. "
                    "You have access to web search, but do not use it unless "
                    "the answer depends on current, changing, externally "
                    "verifiable, or otherwise unavailable information. "
                    "If search is needed, prefer authoritative primary sources. "
                    "If stable internal knowledge is sufficient, answer directly."
                )
            else:
                search_instruction = (
                    "Answer the user's request completely. "
                    "Use web search when the request depends on current, recent, "
                    "changing, externally verifiable, or otherwise unavailable "
                    "information. For stable knowledge, reasoning, writing, or "
                    "explanation that does not require fresh facts, answer directly. "
                    "When searching, prefer reliable primary and authoritative sources."
                )

            claude_messages: list[dict[str, Any]] = []

            if messages:
                for message in messages[-2:]:
                    role = message.get("role")
                    content = message.get("content")

                    if role not in {
                        "user",
                        "assistant",
                    }:
                        continue

                    if not isinstance(
                        content,
                        str,
                    ):
                        continue

                    content = content.strip()

                    if not content:
                        continue

                    if (
                        role == "user"
                        and content == query
                    ):
                        continue

                    if len(content) > 800:
                        content = content[:800]

                    claude_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            claude_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            print(
                "⚡ Claude Native Search mode:",
                search_mode,
            )
            print(
                "🧩 Claude Native Search context turns:",
                max(
                    0,
                    len(claude_messages) - 1,
                ),
            )

            request_args: dict[str, Any] = {
                "model": self.config.model_id,
                "max_tokens": max_tokens,
                "system": (
                    search_instruction
                    + " Use recent conversation context when the latest "
                    "message depends on previous turns. Do not change the "
                    "user's intended subject."
                ),
                "messages": claude_messages,
                "tools": [
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": max_uses,
                    }
                ],
            }

            full_answer = ""

            with self.client.messages.stream(
                **request_args
            ) as stream:

                for text_delta in stream.text_stream:
                    if not text_delta:
                        continue

                    full_answer += text_delta

                    yield (
                        "delta",
                        text_delta,
                    )

                final_message = (
                    stream.get_final_message()
                )

            used_web_search = False
            native_results: list[
                NativeSearchResult
            ] = []
            seen_urls: set[str] = set()

            for block in getattr(
                final_message,
                "content",
                [],
            ):
                block_type = getattr(
                    block,
                    "type",
                    "",
                )

                if block_type == "server_tool_use":
                    if (
                        getattr(
                            block,
                            "name",
                            "",
                        )
                        == "web_search"
                    ):
                        used_web_search = True
                    continue

                if block_type == "web_search_tool_result":
                    used_web_search = True

                    result_content = getattr(
                        block,
                        "content",
                        None,
                    )

                    if isinstance(
                        result_content,
                        list,
                    ):
                        for search_result in result_content:
                            if (
                                getattr(
                                    search_result,
                                    "type",
                                    "",
                                )
                                != "web_search_result"
                            ):
                                continue

                            url = (
                                getattr(
                                    search_result,
                                    "url",
                                    "",
                                )
                                or ""
                            ).strip()

                            title = (
                                getattr(
                                    search_result,
                                    "title",
                                    "",
                                )
                                or ""
                            ).strip()

                            if not url:
                                continue

                            normalized_url = (
                                url
                                .rstrip("/")
                                .casefold()
                            )

                            if normalized_url in seen_urls:
                                continue

                            seen_urls.add(
                                normalized_url
                            )

                            native_results.append(
                                NativeSearchResult(
                                    title=title,
                                    url=url,
                                    source="Claude Web Search",
                                )
                            )

                    continue

                if block_type != "text":
                    continue

                citations = (
                    getattr(
                        block,
                        "citations",
                        None,
                    )
                    or []
                )

                for citation in citations:
                    if (
                        getattr(
                            citation,
                            "type",
                            "",
                        )
                        != "web_search_result_location"
                    ):
                        continue

                    used_web_search = True

                    url = (
                        getattr(
                            citation,
                            "url",
                            "",
                        )
                        or ""
                    ).strip()

                    title = (
                        getattr(
                            citation,
                            "title",
                            "",
                        )
                        or ""
                    ).strip()

                    if not url:
                        continue

                    normalized_url = (
                        url
                        .rstrip("/")
                        .casefold()
                    )

                    if normalized_url in seen_urls:
                        continue

                    seen_urls.add(
                        normalized_url
                    )

                    native_results.append(
                        NativeSearchResult(
                            title=title,
                            url=url,
                            source="Claude Web Search",
                        )
                    )

            native_results = native_results[
                :max_results
            ]

            answer = full_answer.strip()

            usage = getattr(
                final_message,
                "usage",
                None,
            )

            usage_dict = None

            if usage is not None:
                input_tokens = int(
                    getattr(
                        usage,
                        "input_tokens",
                        0,
                    )
                    or 0
                )
                output_tokens = int(
                    getattr(
                        usage,
                        "output_tokens",
                        0,
                    )
                    or 0
                )
                usage_dict = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": (
                        input_tokens
                        + output_tokens
                    ),
                    "cache_read_input_tokens": int(
                        getattr(
                            usage,
                            "cache_read_input_tokens",
                            0,
                        )
                        or 0
                    ),
                    "cache_creation_input_tokens": int(
                        getattr(
                            usage,
                            "cache_creation_input_tokens",
                            0,
                        )
                        or 0
                    ),
                }

            print(
                "🔎 Claude native stream:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                    "stop_reason": getattr(
                        final_message,
                        "stop_reason",
                        None,
                    ),
                },
            )

            if not answer:
                response = NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    error=(
                        "Claude streaming request "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )
            elif (
                not used_web_search
                and not allow_no_search
            ):
                response = NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    answer=answer,
                    results=native_results,
                    error=(
                        "Claude returned without using "
                        "the native web search tool."
                    ),
                    should_fallback=True,
                )
            else:
                response = NativeSearchResponse(
                    success=True,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    answer=answer,
                    should_fallback=False,
                )

            if usage_dict is not None:
                try:
                    response.usage = usage_dict
                except Exception:
                    pass

            yield (
                "complete",
                response,
            )

        except Exception as error:
            print(
                "❌ Claude native streaming failed:",
                repr(error),
            )

            yield (
                "complete",
                NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    error=str(error),
                    should_fallback=True,
                ),
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
            # ==================================================
            # 构造最近圆桌 / 对话上下文
            # ==================================================
            context_lines: list[str] = []

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

                    # 防止历史长回答占满上下文
                    if len(content) > 1500:
                        content = content[:1500]

                    context_lines.append(
                        f"{role.upper()}: {content}"
                    )

            context_text = "\n".join(
                context_lines
            )

            # ==================================================
            # 当前搜索任务
            # ==================================================
            user_content = (
                "Perform live web research for the current request.\n\n"
            )

            if context_text:
                user_content += (
                    "Recent conversation context:\n"
                    f"{context_text}\n\n"
                )

            user_content += (
                "Current request:\n"
                f"{query}"
            )

            system_prompt = (
                "You are Claude performing live web research "
                "for the current user request. "
                "Use web search before answering when current "
                "or changing information is required. "
                "Prefer reliable primary and authoritative sources "
                "for factual claims when available. "
                "Do not rely on stale internal knowledge when "
                "live information is required. "
                "If reliable sources conflict or evidence is "
                "insufficient, explain the uncertainty instead "
                "of guessing."
            )

            # ==================================================
            # Claude 原生 Web Search
            # ==================================================
            response = self.client.messages.create(
                model=self.config.model_id,
                max_tokens=1800,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_content,
                    }
                ],
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 5,
                    }
                ],
            )

            # ==================================================
            # 解析最终回答 + 判断是否真的使用 Web Search
            # ==================================================
            answer_parts: list[str] = []

            used_web_search = False

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            for block in response.content:
                block_type = getattr(
                    block,
                    "type",
                    "",
                )

                # ----------------------------------------------
                # Claude 实际发起 Web Search
                # ----------------------------------------------
                if block_type == "server_tool_use":
                    tool_name = getattr(
                        block,
                        "name",
                        "",
                    )

                    if tool_name == "web_search":
                        used_web_search = True

                    continue

                # ----------------------------------------------
                # Web Search 原始结果
                # ----------------------------------------------
                if block_type == "web_search_tool_result":
                    used_web_search = True

                    result_content = getattr(
                        block,
                        "content",
                        None,
                    )

                    if isinstance(result_content, list):
                        for search_result in result_content:
                            result_type = getattr(
                                search_result,
                                "type",
                                "",
                            )

                            if result_type != "web_search_result":
                                continue

                            url = (
                                getattr(
                                    search_result,
                                    "url",
                                    "",
                                )
                                or ""
                            ).strip()

                            title = (
                                getattr(
                                    search_result,
                                    "title",
                                    "",
                                )
                                or ""
                            ).strip()

                            if not url:
                                continue

                            normalized_url = (
                                url
                                .rstrip("/")
                                .casefold()
                            )

                            if normalized_url in seen_urls:
                                continue

                            seen_urls.add(
                                normalized_url
                            )

                            native_results.append(
                                NativeSearchResult(
                                    title=title,
                                    url=url,
                                    source="Claude Web Search",
                                )
                            )

                    continue

                # ----------------------------------------------
                # Claude 最终文本 + citations
                # ----------------------------------------------
                if block_type == "text":
                    text = (
                        getattr(
                            block,
                            "text",
                            "",
                        )
                        or ""
                    )

                    if text:
                        answer_parts.append(text)

                    citations = (
                        getattr(
                            block,
                            "citations",
                            None,
                        )
                        or []
                    )

                    for citation in citations:
                        citation_type = getattr(
                            citation,
                            "type",
                            "",
                        )

                        if (
                            citation_type
                            != "web_search_result_location"
                        ):
                            continue

                        used_web_search = True

                        url = (
                            getattr(
                                citation,
                                "url",
                                "",
                            )
                            or ""
                        ).strip()

                        title = (
                            getattr(
                                citation,
                                "title",
                                "",
                            )
                            or ""
                        ).strip()

                        if not url:
                            continue

                        normalized_url = (
                            url
                            .rstrip("/")
                            .casefold()
                        )

                        if normalized_url in seen_urls:
                            continue

                        seen_urls.add(
                            normalized_url
                        )

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Claude Web Search",
                            )
                        )

            answer = "\n".join(
                answer_parts
            ).strip()

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 Claude native search:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                    "stop_reason": getattr(
                        response,
                        "stop_reason",
                        None,
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
                    answer=answer,
                    results=native_results,
                    error=(
                        "Claude returned without using "
                        "the native web search tool."
                    ),
                    should_fallback=True,
                )

            if not answer:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    error=(
                        "Claude native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ Claude native search succeeded: "
                f"{len(native_results)} visible sources"
            )

            return NativeSearchResponse(
                success=True,
                model_name=self.model_name,
                provider=self.provider,
                query=query,
                results=native_results,
                answer=answer,
                should_fallback=False,
            )

        except Exception as error:
            print(
                "❌ Claude native search failed:",
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