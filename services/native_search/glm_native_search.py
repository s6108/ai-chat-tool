from __future__ import annotations

from typing import Any, Iterator

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
            raise RuntimeError("Zhipu API key is missing.")

        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=90.0,
            max_retries=1,
        )

    def _build_messages(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        glm_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "Perform live web research before answering the current user request. "
                    "The upstream search-decision system has already determined that this "
                    "request requires current web information, so you MUST use web search. "
                    "Prefer current, reliable, primary and authoritative sources. "
                    "For time-sensitive facts, do not rely on stale internal knowledge. "
                    "Conversation history may contain claims from different AI models. "
                    "Treat them as context, not verified facts."
                ),
            }
        ]

        history = list(messages[-8:]) if messages else []

        if history:
            last = history[-1]
            if (
                last.get("role") == "user"
                and isinstance(last.get("content"), str)
                and last["content"].strip() == query
            ):
                history = history[:-1]

        for message in history:
            role = message.get("role")
            content = message.get("content")

            if role not in {"user", "assistant"}:
                continue
            if not isinstance(content, str):
                continue

            content = content.strip()
            if not content:
                continue
            if len(content) > 1500:
                content = content[:1500]

            glm_messages.append({"role": role, "content": content})

        glm_messages.append({"role": "user", "content": query})
        return glm_messages

    def _collect_sources_from_value(
        self,
        value: Any,
        *,
        results: list[NativeSearchResult],
        seen_urls: set[str],
    ) -> bool:
        used_web_search = False

        if isinstance(value, dict):
            value_type = value.get("type") or ""
            if value_type == "web_search":
                used_web_search = True

            url = value.get("url") or value.get("link") or ""
            if isinstance(url, str):
                url = url.strip()
                if url.startswith(("http://", "https://")):
                    normalized_url = url.rstrip("/").casefold()
                    if normalized_url not in seen_urls:
                        seen_urls.add(normalized_url)
                        title = value.get("title") or value.get("name") or ""
                        if not isinstance(title, str):
                            title = ""
                        results.append(
                            NativeSearchResult(
                                title=title.strip(),
                                url=url,
                                source="GLM Web Search",
                            )
                        )
                        used_web_search = True

            for nested_value in value.values():
                if self._collect_sources_from_value(
                    nested_value,
                    results=results,
                    seen_urls=seen_urls,
                ):
                    used_web_search = True

            return used_web_search

        if isinstance(value, list):
            for item in value:
                if self._collect_sources_from_value(
                    item,
                    results=results,
                    seen_urls=seen_urls,
                ):
                    used_web_search = True

        return used_web_search

    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        allow_no_search: bool = False,
    ) -> Iterator[tuple[str, Any]]:
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
                    should_fallback=False,
                ),
            )
            return

        try:
            glm_messages = self._build_messages(query=query, messages=messages)

            print("⚡ GLM Native Search streaming")
            print(
                "🧩 GLM Native Search context turns:",
                len(glm_messages) - 2,
            )

            stream = self.client.chat.completions.create(
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
                stream=True,
            )

            answer_parts: list[str] = []
            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()
            used_web_search = False

            for chunk in stream:
                if hasattr(chunk, "model_dump"):
                    raw_chunk = chunk.model_dump()
                    if self._collect_sources_from_value(
                        raw_chunk,
                        results=native_results,
                        seen_urls=seen_urls,
                    ):
                        used_web_search = True

                if not getattr(chunk, "choices", None):
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                content = getattr(delta, "content", None)
                if isinstance(content, str) and content:
                    answer_parts.append(content)
                    yield ("delta", content)

                if hasattr(choice, "model_dump"):
                    raw_choice = choice.model_dump()
                    if self._collect_sources_from_value(
                        raw_choice,
                        results=native_results,
                        seen_urls=seen_urls,
                    ):
                        used_web_search = True

            answer = "".join(answer_parts).strip()
            native_results = native_results[:max_results]

            if native_results:
                used_web_search = True

            print(
                "🔎 GLM native stream:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                },
            )

            if not used_web_search and not allow_no_search:
                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        answer=answer,
                        results=native_results,
                        error="GLM returned without detectable native web search results.",
                        should_fallback=False,
                    ),
                )
                return

            if not answer:
                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        results=native_results,
                        error="GLM native web search produced no final answer.",
                        should_fallback=False,
                    ),
                )
                return

            print(
                f"✅ GLM native streaming search succeeded: "
                f"{len(native_results)} visible sources"
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
            print("❌ GLM native streaming failed:", repr(error))
            yield (
                "complete",
                NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    error=str(error),
                    should_fallback=False,
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
            glm_messages = self._build_messages(query=query, messages=messages)

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
                raise RuntimeError("GLM returned no choices.")

            message = response.choices[0].message
            answer = message.content or ""
            if not isinstance(answer, str):
                answer = str(answer)
            answer = answer.strip()

            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()
            used_web_search = False

            raw_data: dict[str, Any] = {}
            if hasattr(response, "model_dump"):
                raw_data = response.model_dump()

            web_search_results = raw_data.get("web_search")
            if isinstance(web_search_results, list):
                if web_search_results:
                    used_web_search = True

                for item in web_search_results:
                    if not isinstance(item, dict):
                        continue

                    url = item.get("link") or item.get("url") or ""
                    if not isinstance(url, str):
                        continue

                    url = url.strip()
                    if not url.startswith(("http://", "https://")):
                        continue

                    normalized_url = url.rstrip("/").casefold()
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

            if self._collect_sources_from_value(
                raw_data,
                results=native_results,
                seen_urls=seen_urls,
            ):
                used_web_search = True

            if native_results:
                used_web_search = True

            native_results = native_results[:max_results]

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
                    error="GLM returned without detectable native web search results.",
                    should_fallback=True,
                )

            if not answer:
                return NativeSearchResponse(
                    success=False,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=native_results,
                    error="GLM native web search produced no final answer.",
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
            print("❌ GLM native search failed:", repr(error))
            return NativeSearchResponse(
                success=False,
                model_name=self.model_name,
                provider=self.provider,
                query=query,
                error=str(error),
                should_fallback=True,
            )
