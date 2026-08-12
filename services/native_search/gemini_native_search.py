from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class GeminiNativeSearch(BaseNativeSearch):
    """
    Gemini 原生搜索 Adapter。

    使用 Gemini API 自带的 Google Search Grounding。

    本文件只负责 Gemini 自己的原生搜索。
    如果失败，由 Megor 上层进入 Tavily Safety Net。
    """

    model_name = "Gemini"
    provider = "google"

    def __init__(self) -> None:
        self.config = get_model_config("Gemini")

        if not self.config.api_key:
            raise RuntimeError(
                "Gemini API key is missing."
            )

        self.client = genai.Client(
            api_key=self.config.api_key,
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
            # 构造最近对话上下文
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

                    if len(content) > 1500:
                        content = content[:1500]

                    context_lines.append(
                        f"{role.upper()}: {content}"
                    )

            context_text = "\n".join(
                context_lines
            )

            # ==================================================
            # 给 Gemini 的完整搜索任务
            # ==================================================
            search_prompt = (
                "Perform live research using Google Search "
                "for the current user request.\n\n"
                "Use current web information before answering.\n"
                "Prefer reliable primary and authoritative "
                "sources for factual claims.\n"
                "Do not rely on stale internal knowledge when "
                "the question requires current information.\n"
                "If sources conflict, explain the uncertainty "
                "rather than guessing.\n\n"
            )

            if context_text:
                search_prompt += (
                    "Recent conversation context:\n"
                    f"{context_text}\n\n"
                )

            search_prompt += (
                "Current request:\n"
                f"{query}"
            )

            # ==================================================
            # Gemini 原生 Google Search
            # ==================================================
            grounding_tool = types.Tool(
                google_search=types.GoogleSearch()
            )

            response = self.client.models.generate_content(
                model=self.config.model_id,
                contents=search_prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        grounding_tool,
                    ],
                ),
            )

            answer = (
                getattr(
                    response,
                    "text",
                    "",
                )
                or ""
            ).strip()

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            used_google_search = False

            # ==================================================
            # 读取 Grounding Metadata
            # ==================================================
            candidates = (
                getattr(
                    response,
                    "candidates",
                    None,
                )
                or []
            )

            for candidate in candidates:
                grounding_metadata = getattr(
                    candidate,
                    "grounding_metadata",
                    None,
                )

                if grounding_metadata is None:
                    continue

                # 如果存在 grounding metadata，
                # 基本说明 Google Search grounding 已参与。
                search_queries = (
                    getattr(
                        grounding_metadata,
                        "web_search_queries",
                        None,
                    )
                    or []
                )

                grounding_chunks = (
                    getattr(
                        grounding_metadata,
                        "grounding_chunks",
                        None,
                    )
                    or []
                )

                if search_queries or grounding_chunks:
                    used_google_search = True

                # ==================================================
                # 提取 Google Search 来源
                # ==================================================
                for chunk in grounding_chunks:
                    web = getattr(
                        chunk,
                        "web",
                        None,
                    )

                    if web is None:
                        continue

                    url = (
                        getattr(
                            web,
                            "uri",
                            "",
                        )
                        or ""
                    ).strip()

                    title = (
                        getattr(
                            web,
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
                            source="Google Search",
                        )
                    )

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 Gemini native search:",
                {
                    "google_search": used_google_search,
                    "sources": len(native_results),
                },
            )

            # ==================================================
            # 安全判断
            # ==================================================
            if not used_google_search:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    answer=answer,
                    results=native_results,
                    error=(
                        "Gemini returned without using "
                        "Google Search grounding."
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
                        "Gemini Google Search grounding "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ Gemini native search succeeded: "
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
                "❌ Gemini native search failed:",
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