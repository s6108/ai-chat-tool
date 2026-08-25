from __future__ import annotations

from typing import Any

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class GrokNativeSearch(BaseNativeSearch):
    """
    Grok 原生搜索 Adapter。

    优先使用 xAI 自己的：
    - Web Search
    - X Search

    本文件绝不调用 Tavily。
    原生搜索失败后，由 Megor 上层决定是否进入 Tavily Safety Net。
    """

    model_name = "Grok"
    provider = "xai"

    def __init__(self) -> None:
        self.config = get_model_config("Grok")

        if not self.config.api_key:
            raise RuntimeError(
                "Grok API key is missing."
            )

        self.client = OpenAI(
            api_key=self.config.api_key,
            base_url="https://api.x.ai/v1",
            timeout=35.0,
            max_retries=0,
        )

        # 保存最近一次 Grok 原生搜索的真实 usage / cost
        self.last_usage = None

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
        xAI Responses API + Web/X Search true streaming.

        yield:
            ("delta", text)
            ("complete", NativeSearchResponse)

        In unified mode Grok may answer without invoking a search tool.
        """

        self.last_usage = None
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
            is_fast_search = search_mode == "fast"

            if is_fast_search:
                instruction = (
                    "Answer the user's request directly and concisely. "
                    "Use native web_search or x_search only when the answer "
                    "depends on current, changing, externally verifiable, "
                    "or otherwise unavailable information. If stable internal "
                    "knowledge is sufficient, answer directly without search. "
                    "Prefer authoritative primary sources when searching."
                )
            else:
                instruction = (
                    "Answer the user's request completely and analytically. "
                    "Use native web_search or x_search when current, recent, "
                    "changing, externally verifiable, social, or otherwise "
                    "unavailable information is needed. Stable reasoning and "
                    "knowledge may be answered directly. Prefer reliable "
                    "primary and authoritative sources when searching."
                )

            input_messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        instruction
                        + " Use recent conversation context when the latest "
                        "request depends on previous turns. Do not change the "
                        "user's intended subject."
                    ),
                }
            ]

            recent_context: list[dict[str, Any]] = []

            if messages:
                for message in messages[-2:]:
                    role = message.get("role")
                    content = message.get("content")

                    if role not in {"user", "assistant"}:
                        continue
                    if not isinstance(content, str):
                        continue

                    content = content.strip()
                    if not content:
                        continue
                    if role == "user" and content == query:
                        continue
                    if len(content) > 800:
                        content = content[:800]

                    recent_context.append(
                        {"role": role, "content": content}
                    )

            input_messages.extend(recent_context)
            input_messages.append(
                {"role": "user", "content": query}
            )

            print("⚡ Grok Native Search mode:", search_mode)
            print(
                "🧩 Grok Native Search context turns:",
                len(recent_context),
            )

            stream = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {"type": "web_search"},
                    {"type": "x_search"},
                ],
                include=[
                    "web_search_call.action.sources",
                ],
                store=False,
                stream=True,
            )

            full_answer = ""
            final_response = None

            for event in stream:
                event_type = (
                    getattr(event, "type", "") or ""
                )

                if event_type == "response.output_text.delta":
                    delta = (
                        getattr(event, "delta", "") or ""
                    )
                    if delta:
                        full_answer += delta
                        yield ("delta", delta)
                    continue

                if event_type == "response.completed":
                    final_response = getattr(
                        event,
                        "response",
                        None,
                    )

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
                            "Grok native streaming ended "
                            "without response.completed."
                        ),
                        should_fallback=True,
                    ),
                )
                return

            usage = getattr(final_response, "usage", None)

            if usage is not None:
                input_tokens = int(
                    getattr(usage, "input_tokens", 0) or 0
                )
                output_tokens = int(
                    getattr(usage, "output_tokens", 0) or 0
                )
                total_tokens = int(
                    getattr(usage, "total_tokens", 0) or 0
                )
                cost_ticks = int(
                    getattr(usage, "cost_in_usd_ticks", 0) or 0
                )
                provider_cost_usd = (
                    cost_ticks / 10_000_000_000
                )
                server_side_tools = int(
                    getattr(
                        usage,
                        "num_server_side_tools_used",
                        0,
                    )
                    or 0
                )

                self.last_usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_in_usd_ticks": cost_ticks,
                    "provider_cost_usd": provider_cost_usd,
                    "server_side_tools": server_side_tools,
                }

                print(
                    "💳 Grok native usage:",
                    self.last_usage,
                )

            used_web_search = False
            used_x_search = False
            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            output_items = (
                getattr(final_response, "output", None)
                or []
            )

            for item in output_items:
                item_type = getattr(item, "type", "") or ""

                if not item_type and hasattr(item, "model_dump"):
                    dumped = item.model_dump()
                    item_type = dumped.get("type", "") or ""

                if item_type == "web_search_call":
                    used_web_search = True
                    action = getattr(item, "action", None)
                    sources = (
                        getattr(action, "sources", None)
                        or []
                    )

                    for source in sources:
                        url = (
                            getattr(source, "url", "") or ""
                        ).strip()
                        title = (
                            getattr(source, "title", "") or ""
                        ).strip()

                        if not url:
                            continue

                        normalized_url = (
                            url.rstrip("/").casefold()
                        )
                        if normalized_url in seen_urls:
                            continue

                        seen_urls.add(normalized_url)
                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Web",
                            )
                        )

                elif item_type == "x_search_call":
                    used_x_search = True

            for item in output_items:
                if getattr(item, "type", "") != "message":
                    continue

                for content_item in (
                    getattr(item, "content", None) or []
                ):
                    if (
                        getattr(content_item, "type", "")
                        != "output_text"
                    ):
                        continue

                    for annotation in (
                        getattr(
                            content_item,
                            "annotations",
                            None,
                        )
                        or []
                    ):
                        url = (
                            getattr(annotation, "url", "") or ""
                        ).strip()
                        title = (
                            getattr(annotation, "title", "") or ""
                        ).strip()

                        if not url:
                            continue

                        normalized_url = (
                            url.rstrip("/").casefold()
                        )
                        if normalized_url in seen_urls:
                            continue

                        seen_urls.add(normalized_url)

                        source_type = (
                            "X"
                            if "x.com/" in normalized_url
                            else "Web"
                        )
                        if source_type == "X":
                            used_x_search = True

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source=source_type,
                            )
                        )

            native_results = native_results[:max_results]

            print(
                "🔎 Grok native stream:",
                {
                    "web_search": used_web_search,
                    "x_search": used_x_search,
                    "sources": len(native_results),
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
                        "Grok native streaming produced "
                        "no final answer."
                    ),
                    should_fallback=True,
                    usage=self.last_usage,
                )
            elif (
                not used_web_search
                and not used_x_search
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
                        "Grok returned without using "
                        "a native search tool."
                    ),
                    should_fallback=True,
                    usage=self.last_usage,
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
                    usage=self.last_usage,
                )

            yield ("complete", response)

        except Exception as error:
            print(
                "❌ Grok native streaming failed:",
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
                    usage=self.last_usage,
                ),
            )


    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
    ) -> NativeSearchResponse:

        self.last_usage = None

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
            # 最近圆桌 / 对话上下文
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

                    # 防止长历史占满上下文
                    if len(content) > 1500:
                        content = content[:1500]

                    input_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            # ==================================================
            # 原生搜索任务
            # ==================================================
            input_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Perform live research for the user's current request. "
                        "Use the available native search tools before answering. "
                        "For factual claims, prefer current, reliable, primary "
                        "and authoritative sources when available. "
                        "Use X Search when real-time public discussion, "
                        "social reaction, statements, or posts are relevant. "
                        "Do not rely on stale internal knowledge when current "
                        "information is required."
                    ),
                }
            )

            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            # ==================================================
            # xAI Responses API
            # ==================================================
            response = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                    },
                    {
                        "type": "x_search",
                    },
                ],
                include=[
                    "web_search_call.action.sources",
                ],
                store=False,
            )

            

            # ==================================================
            # xAI real usage / billed cost
            # ==================================================

            usage = getattr(
                response,
                "usage",
                None,
            )

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

                total_tokens = int(
                    getattr(
                        usage,
                        "total_tokens",
                        0,
                    )
                    or 0
                )

                cost_ticks = int(
                    getattr(
                        usage,
                        "cost_in_usd_ticks",
                        0,
                    )
                    or 0
                )

                provider_cost_usd = (
                    cost_ticks
                    / 10_000_000_000
                )

                server_side_tools = int(
                    getattr(
                        usage,
                        "num_server_side_tools_used",
                        0,
                    )
                    or 0
                )

                self.last_usage = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_in_usd_ticks": cost_ticks,
                    "provider_cost_usd": provider_cost_usd,
                    "server_side_tools": server_side_tools,
                }

                print(
                    "💳 Grok native usage:",
                    self.last_usage,
                )

            # ==================================================
            # 最终回答文本
            # ==================================================
            answer = (
                getattr(
                    response,
                    "output_text",
                    "",
                )
                or ""
            ).strip()

            # ==================================================
            # 检查 Grok 是否真的执行了原生搜索
            # ==================================================
            used_web_search = False
            used_x_search = False

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

            for item in output_items:
                item_type = getattr(item, "type", "") or ""

                # 兼容不同 SDK / response object 映射
                if not item_type and hasattr(item, "model_dump"):
                    dumped = item.model_dump()
                    item_type = dumped.get("type", "") or ""

                if item_type == "web_search_call":
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

                        seen_urls.add(normalized_url)

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Web",
                            )
                        )

                elif item_type == "x_search_call":
                    used_x_search = True
            # ==================================================
            # 也从最终回答 annotations 中提取引用 URL
            # 防止部分来源没有出现在 action.sources
            # ==================================================
            for item in output_items:
                if getattr(item, "type", "") != "message":
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

                        source_type = (
                            "X"
                            if "x.com/" in normalized_url
                            else "Web"
                        )
                        if source_type == "X":
                            used_x_search = True
                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source=source_type,
                            )
                        )

            # 限制最终保留来源数量
            native_results = native_results[:max_results]

            print(
                "🔎 Grok native search:",
                {
                    "web_search": used_web_search,
                    "x_search": used_x_search,
                    "sources": len(native_results),
                },
            )

            # ==================================================
            # 安全判断
            # ==================================================

            # 没有执行任何原生搜索工具
            if not used_web_search and not used_x_search:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    answer=answer,
                    results=native_results,
                    error=(
                        "Grok returned without using "
                        "a native search tool."
                    ),
                    should_fallback=True,
                )

            # 搜索了，但没有最终回答
            if not answer:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    error=(
                        "Grok native search produced "
                        "no final answer."
                    ),
                    should_fallback=True,
                )

            # Web/X 搜索已经实际执行。
            # 即使部分 X Search 没暴露标准 URL，
            # 也不能因此误判为“没有搜索”。
            print(
                f"✅ Grok native search succeeded: "
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
                usage=self.last_usage,
            )

        except Exception as error:
            print(
                "❌ Grok native search failed:",
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