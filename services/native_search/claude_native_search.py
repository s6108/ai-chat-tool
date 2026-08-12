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