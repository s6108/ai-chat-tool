from __future__ import annotations

from typing import Any

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class OpenAINativeSearch(BaseNativeSearch):
    """
    OpenAI 原生 Web Search Adapter。

    使用 OpenAI Responses API + Web Search。

    本文件只负责 OpenAI 自己的原生搜索。
    原生搜索失败时，由 Megor 上层进入 Tavily Safety Net。
    """

    model_name = "ChatGPT"
    provider = "openai"

    def __init__(self) -> None:
        self.config = get_model_config("ChatGPT")

        if not self.config.api_key:
            raise RuntimeError(
                "OpenAI API key is missing."
            )

        self.client = OpenAI(
            api_key=self.config.api_key,
            timeout=60.0,
        )

    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        search_mode: str = "research",
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
            input_messages: list[dict[str, Any]] = []

        
            # ==================================================
            # 原生搜索模式
            # ==================================================

            is_fast_search = (
                search_mode == "fast"
            )

            if is_fast_search:
                search_instruction = (
                    "Perform a focused live web search to answer "
                    "the user's current factual question. "
                    "Prefer one or a few authoritative primary sources. "
                    "Return a concise direct answer. "
                    "Do not perform broad research or lengthy analysis. "
                    "Verify the current fact before answering."
                )
            else:
                search_instruction = (
                    "Perform live web research before answering "
                    "the current user request. "
                    "Prefer current, reliable, primary and "
                    "authoritative sources. "
                    "For time-sensitive facts, do not rely on "
                    "stale internal knowledge. "
                    "Compare relevant evidence when appropriate "
                    "and provide a sufficiently complete answer."
                )

            # ==================================================
            # 唯一 system message
            # ==================================================

            input_messages.append(
                {
                    "role": "system",
                    "content": search_instruction,
                }
            )

            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            # ==================================================
            # OpenAI Responses API + Web Search
            # ==================================================
            response = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                    }
                ],
                include=[
                    "web_search_call.action.sources",
                ],
                store=False,
            )

            answer = (
                getattr(
                    response,
                    "output_text",
                    "",
                )
                or ""
            ).strip()

            used_web_search = False

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            output_items = (
                getattr(
                    response,
                    "output",
                    None,
                )
                or []
            )

            # ==================================================
            # 检查 Web Search tool call + 提取 sources
            # ==================================================
            for item in output_items:
                item_type = (
                    getattr(
                        item,
                        "type",
                        "",
                    )
                    or ""
                )

                if (
                    not item_type
                    and hasattr(item, "model_dump")
                ):
                    dumped = item.model_dump()
                    item_type = (
                        dumped.get("type", "")
                        or ""
                    )

                if item_type != "web_search_call":
                    continue

                used_web_search = True

                action = getattr(
                    item,
                    "action",
                    None,
                )

                sources = (
                    getattr(
                        action,
                        "sources",
                        None,
                    )
                    or []
                )

                for source in sources:
                    url = (
                        getattr(
                            source,
                            "url",
                            "",
                        )
                        or ""
                    ).strip()

                    title = (
                        getattr(
                            source,
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
                            source="OpenAI Web Search",
                        )
                    )

            # ==================================================
            # 再从最终文本 annotations 提取引用
            # ==================================================
            for item in output_items:
                if (
                    getattr(item, "type", "")
                    != "message"
                ):
                    continue

                contents = (
                    getattr(
                        item,
                        "content",
                        None,
                    )
                    or []
                )

                for content_item in contents:
                    if (
                        getattr(
                            content_item,
                            "type",
                            "",
                        )
                        != "output_text"
                    ):
                        continue

                    annotations = (
                        getattr(
                            content_item,
                            "annotations",
                            None,
                        )
                        or []
                    )

                    for annotation in annotations:
                        url = (
                            getattr(
                                annotation,
                                "url",
                                "",
                            )
                            or ""
                        ).strip()

                        title = (
                            getattr(
                                annotation,
                                "title",
                                "",
                            )
                            or ""
                        ).strip()

                        if not url:
                            continue

                        used_web_search = True

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
                                source="OpenAI Web Search",
                            )
                        )

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 OpenAI native search:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
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
                        "OpenAI returned without using "
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
                        "OpenAI native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ OpenAI native search succeeded: "
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
                "❌ OpenAI native search failed:",
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

    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        search_mode: str = "research",
    ):
        """
        OpenAI Responses API + Web Search 真正流式输出。

        yield:
            ("delta", text)
                模型真实输出的文本增量。

            ("complete", NativeSearchResponse)
                流结束后的完整搜索结果，
                包含最终答案、sources、success/fallback 状态。
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
            # ==================================================
            # 搜索模式
            # ==================================================

            is_fast_search = (
                search_mode == "fast"
            )

            # ==================================================
            # Web Search 上下文强度
            #
            # fast:
            #   简单当前事实，只取较小搜索上下文，
            #   目标是缩短搜索到首个文本 delta 的时间。
            #
            # research:
            #   保留 medium，兼顾速度与综合分析质量。
            # ==================================================

            search_context_size = (
                "low"
                if is_fast_search
                else "medium"
            )

            print(
                "⚡ OpenAI Web Search context:",
                search_context_size,
            )

            if is_fast_search:
                search_instruction = (
                    "Answer the user's request directly and concisely. "
                    "You have access to web search, but do not use it unless "
                    "the answer depends on current, changing, externally "
                    "verifiable, or otherwise unavailable information. "
                    "If web search is needed, prefer authoritative primary "
                    "sources and verify the current fact before answering. "
                    "If stable internal knowledge is sufficient, answer "
                    "without calling web search."
                )

            else:
                search_instruction = (
                    "Answer the user's request completely. "
                    "You have access to web search. Use it when the request "
                    "depends on current, recent, changing, externally "
                    "verifiable, or otherwise unavailable information. "
                    "For stable knowledge, reasoning, writing, explanation, "
                    "or other tasks that do not require fresh external facts, "
                    "answer directly without web search. "
                    "When web search is used, prefer current, reliable, "
                    "primary and authoritative sources."
                )

            # ==================================================
            # 输入消息
            #
            # 不再调用额外 AI resolver。
            # 直接给 Native Search 少量最近对话上下文，
            # 让“他呢？ / what about him? / 彼は？ / Et lui ?”
            # 这类任何语言的追问都能自然理解。
            # ==================================================

            input_messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        search_instruction
                        + " Use the recent conversation context when "
                        "the latest user message contains references "
                        "whose meaning depends on previous turns. "
                        "Do not change the user's intended subject."
                    ),
                }
            ]

            recent_context: list[dict[str, Any]] = []

            if messages:

                for message in messages[-24:]:

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

                    # 当前 query 会在最后单独加入，
                    # 避免重复发送同一个用户问题。
                    if (
                        role == "user"
                        and content == query
                    ):
                        continue

                   

                    recent_context.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            input_messages.extend(
                recent_context
            )

            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            print(
                "🧩 OpenAI Native Search context turns:",
                len(recent_context),
            )

            # ==================================================
            # 真正的 Responses API Streaming
            # ==================================================

            stream = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": search_context_size,
                    }
                ],
                include=[
                    "web_search_call.action.sources",
                ],
                store=False,
                stream=True,
            )

            full_answer = ""
            final_response = None

            # ==================================================
            # 消费 OpenAI streaming events
            # ==================================================

            for event in stream:

                event_type = (
                    getattr(
                        event,
                        "type",
                        "",
                    )
                    or ""
                )

                # ----------------------------------------------
                # 真正的模型文本增量
                # ----------------------------------------------

                if (
                    event_type
                    == "response.output_text.delta"
                ):
                    delta = (
                        getattr(
                            event,
                            "delta",
                            "",
                        )
                        or ""
                    )

                    if delta:
                        full_answer += delta

                        yield (
                            "delta",
                            delta,
                        )

                    continue

                # ----------------------------------------------
                # 最终完整 Response
                # ----------------------------------------------

                if (
                    event_type
                    == "response.completed"
                ):
                    final_response = getattr(
                        event,
                        "response",
                        None,
                    )

            # ==================================================
            # Streaming 结束
            # ==================================================

            answer = full_answer.strip()

            if final_response is None:
                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        answer=answer,
                        error=(
                            "OpenAI native streaming ended "
                            "without response.completed."
                        ),
                        should_fallback=True,
                    ),
                )
                return

            # ==================================================
            # 提取 Web Search sources
            # ==================================================

            used_web_search = False

            native_results: list[
                NativeSearchResult
            ] = []

            seen_urls: set[str] = set()

            output_items = (
                getattr(
                    final_response,
                    "output",
                    None,
                )
                or []
            )

            # ----------------------------------------------
            # web_search_call.action.sources
            # ----------------------------------------------

            for item in output_items:

                item_type = (
                    getattr(
                        item,
                        "type",
                        "",
                    )
                    or ""
                )

                if (
                    not item_type
                    and hasattr(
                        item,
                        "model_dump",
                    )
                ):
                    dumped = item.model_dump()

                    item_type = (
                        dumped.get(
                            "type",
                            "",
                        )
                        or ""
                    )

                if (
                    item_type
                    != "web_search_call"
                ):
                    continue

                used_web_search = True

                action = getattr(
                    item,
                    "action",
                    None,
                )

                sources = (
                    getattr(
                        action,
                        "sources",
                        None,
                    )
                    or []
                )

                for source in sources:

                    url = (
                        getattr(
                            source,
                            "url",
                            "",
                        )
                        or ""
                    ).strip()

                    title = (
                        getattr(
                            source,
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

                    if (
                        normalized_url
                        in seen_urls
                    ):
                        continue

                    seen_urls.add(
                        normalized_url
                    )

                    native_results.append(
                        NativeSearchResult(
                            title=title,
                            url=url,
                            source=(
                                "OpenAI Web Search"
                            ),
                        )
                    )

            # ----------------------------------------------
            # 最终 output_text annotations
            # ----------------------------------------------

            for item in output_items:

                if (
                    getattr(
                        item,
                        "type",
                        "",
                    )
                    != "message"
                ):
                    continue

                contents = (
                    getattr(
                        item,
                        "content",
                        None,
                    )
                    or []
                )

                for content_item in contents:

                    if (
                        getattr(
                            content_item,
                            "type",
                            "",
                        )
                        != "output_text"
                    ):
                        continue

                    annotations = (
                        getattr(
                            content_item,
                            "annotations",
                            None,
                        )
                        or []
                    )

                    for annotation in annotations:

                        url = (
                            getattr(
                                annotation,
                                "url",
                                "",
                            )
                            or ""
                        ).strip()

                        title = (
                            getattr(
                                annotation,
                                "title",
                                "",
                            )
                            or ""
                        ).strip()

                        if not url:
                            continue

                        used_web_search = True

                        normalized_url = (
                            url
                            .rstrip("/")
                            .casefold()
                        )

                        if (
                            normalized_url
                            in seen_urls
                        ):
                            continue

                        seen_urls.add(
                            normalized_url
                        )

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source=(
                                    "OpenAI Web Search"
                                ),
                            )
                        )

            native_results = (
                native_results[
                    :max_results
                ]
            )

            print(
                "🔎 OpenAI native stream:",
                {
                    "web_search": (
                        used_web_search
                    ),
                    "sources": len(
                        native_results
                    ),
                },
            )

            # ==================================================
            # 最终安全判断
            # ==================================================

            # In unified ChatGPT mode, not using web search is valid.
            # A stable-knowledge request should complete successfully without
            # forcing Tavily fallback merely because no web_search_call exists.
            if not answer:

                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        results=native_results,
                        error=(
                            "OpenAI native streaming "
                            "produced no final answer."
                        ),
                        should_fallback=True,
                    ),
                )

                return

            print(
                "✅ OpenAI unified streaming succeeded:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                },
            )

            yield (
                "complete",
                NativeSearchResponse(
                    success=True,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    answer=answer,
                    should_fallback=False,
                ),
            )

        except Exception as error:

            print(
                "❌ OpenAI native streaming "
                "search failed:",
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