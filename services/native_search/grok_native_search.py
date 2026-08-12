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
            timeout=60.0,
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