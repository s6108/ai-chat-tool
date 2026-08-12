from __future__ import annotations

from typing import Any

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class QwenNativeSearch(BaseNativeSearch):
    """
    Qwen 原生 Web Search Adapter。

    qwen3.6-flash 使用 Alibaba Cloud Model Studio
    OpenAI-compatible Responses API + web_search。

    原生搜索失败时，由 Megor 上层进入 Tavily Safety Net。
    """

    model_name = "Qwen"
    provider = "dashscope"

    def __init__(self) -> None:
        self.config = get_model_config("Qwen")

        if not self.config.api_key:
            raise RuntimeError(
                "Qwen API key is missing."
            )

        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=60.0,
            max_retries=1,
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
            # Qwen Native Search system instruction
            # 必须是第一条，而且只能有一个 system message
            # ==================================================
            input_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Perform live web research for the current "
                        "user request. Use web search before answering. "
                        "Prefer current, reliable, primary and "
                        "authoritative sources when available. "
                        "For current facts, do not rely on stale "
                        "internal knowledge. "
                        "If sources conflict, explain the uncertainty "
                        "instead of guessing. "
                        "The conversation history below may contain "
                        "statements from different AI models. "
                        "Treat those statements as conversation context, "
                        "not as verified facts. Verify disputed or "
                        "time-sensitive claims with web search."
                    ),
                }
            )

            # ==================================================
            # 最近圆桌 / 对话上下文
            #
            # 注意：
            # 不复制历史 system message。
            # Qwen Responses API 最多允许一个 system，
            # 并且它必须位于 messages 第一条。
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

                    input_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            # ==================================================
            # 当前需要搜索的问题
            # ==================================================
            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            # ==================================================
            # 原生搜索指令
            # ==================================================
            input_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Perform live web research for the current "
                        "user request. Use web search before answering. "
                        "Prefer current, reliable, primary and "
                        "authoritative sources when available. "
                        "For current facts, do not rely on stale "
                        "internal knowledge. If sources conflict, "
                        "explain the uncertainty instead of guessing."
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
            # Qwen Responses API + 原生 Web Search
            # ==================================================
            response = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                    }
                ],
                extra_body={
                    "enable_thinking": False,
                },
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
            # 检测原生 Web Search
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

                        seen_urls.add(
                            normalized_url
                        )

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Qwen Web Search",
                            )
                        )

            # ==================================================
            # 从最终回答 annotations 再提取引用
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
                                source="Qwen Web Search",
                            )
                        )

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 Qwen native search:",
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
                        "Qwen returned without using "
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
                        "Qwen native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ Qwen native search succeeded: "
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
                "❌ Qwen native search failed:",
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