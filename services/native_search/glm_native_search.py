from __future__ import annotations

from typing import Any

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class GLMNativeSearch(BaseNativeSearch):
    """
    GLM / Zhipu 原生 Web Search Adapter。

    用户界面只显示 GLM。
    原生搜索使用 GLM 品牌的文本模型。
    """

    model_name = "GLM"
    provider = "zhipu"

    def __init__(self) -> None:
        self.config = get_model_config("GLM")

        if not self.config.api_key:
            raise RuntimeError(
                "Zhipu API key is missing."
            )

        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=90.0,
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
            glm_messages: list[dict[str, Any]] = []

            # ==================================================
            # 唯一 system message
            # ==================================================
            glm_messages.append(
                {
                    "role": "system",
                    "content": (
                        "Perform live web research before answering "
                        "the current user request. "
                        "Prefer current, reliable, primary and "
                        "authoritative sources. "
                        "For time-sensitive facts, do not rely on "
                        "stale internal knowledge. "
                        "Conversation history may contain claims from "
                        "different AI models. Treat them as context, "
                        "not verified facts. Verify disputed claims "
                        "with web search."
                    ),
                }
            )

            # ==================================================
            # 最近对话上下文
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

                    glm_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            # ==================================================
            # 当前搜索问题
            # ==================================================
            glm_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            # ==================================================
            # 智谱 Chat Completions + Web Search
            # ==================================================
            response = self.client.chat.completions.create(
                model=self.config.model_id,
                messages=glm_messages,
                tools=[
                    {
                        "type": "web_search",
                        "web_search": {
                            "enable": True,
                            "search_result": True,
                        },
                    }
                ],
                stream=False,
            )

            if not response.choices:
                raise RuntimeError(
                    "GLM returned no choices."
                )

            message = response.choices[0].message

            answer = message.content or ""

            if not isinstance(answer, str):
                answer = str(answer)

            answer = answer.strip()

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            used_web_search = False

            # ==================================================
            # 获取完整原始响应
            # ==================================================
            raw_data: dict[str, Any] = {}

            if hasattr(response, "model_dump"):
                raw_data = response.model_dump()

            # ==================================================
            # 1. 优先读取智谱官方顶层 web_search
            # ==================================================
            web_search_results = raw_data.get("web_search")

            if isinstance(web_search_results, list):
                if web_search_results:
                    used_web_search = True

                for item in web_search_results:
                    if not isinstance(item, dict):
                        continue

                    url = (
                        item.get("link")
                        or item.get("url")
                        or ""
                    )

                    if not isinstance(url, str):
                        continue

                    url = url.strip()

                    if not url.startswith(
                        ("http://", "https://")
                    ):
                        continue

                    normalized_url = (
                        url.rstrip("/").casefold()
                    )

                    if normalized_url in seen_urls:
                        continue

                    seen_urls.add(normalized_url)

                    title = item.get("title") or ""

                    if not isinstance(title, str):
                        title = ""

                    native_results.append(
                        NativeSearchResult(
                            title=title.strip(),
                            url=url,
                            source="GLM Web Search",
                        )
                    )

            # ==================================================
            # 2. 兼容不同 SDK / API 返回结构
            # ==================================================
            def walk(value: Any) -> None:
                nonlocal used_web_search

                if isinstance(value, dict):

                    value_type = (
                        value.get("type")
                        or ""
                    )

                    if value_type == "web_search":
                        used_web_search = True

                    url = (
                        value.get("url")
                        or value.get("link")
                        or ""
                    )

                    if isinstance(url, str):
                        url = url.strip()

                        if url.startswith(
                            ("http://", "https://")
                        ):
                            normalized_url = (
                                url.rstrip("/").casefold()
                            )

                            if normalized_url not in seen_urls:
                                seen_urls.add(normalized_url)

                                title = (
                                    value.get("title")
                                    or value.get("name")
                                    or ""
                                )

                                if not isinstance(title, str):
                                    title = ""

                                native_results.append(
                                    NativeSearchResult(
                                        title=title.strip(),
                                        url=url,
                                        source="GLM Web Search",
                                    )
                                )

                    for nested_value in value.values():
                        walk(nested_value)

                    return

                if isinstance(value, list):
                    for item in value:
                        walk(item)


            walk(raw_data)

            # 只要确实拿到搜索来源，就确认原生搜索成功执行
            if native_results:
                used_web_search = True

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 GLM native search:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                },
            )

            if not used_web_search:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    answer=answer,
                    results=native_results,
                    error=(
                        "GLM returned without detectable "
                        "native web search results."
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
                        "GLM native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ GLM native search succeeded: "
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
                "❌ GLM native search failed:",
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