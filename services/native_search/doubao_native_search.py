from __future__ import annotations

from typing import Any, Iterator

from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
    NativeSearchResult,
)


class DoubaoNativeSearch(BaseNativeSearch):
    """
    Doubao 原生 Web Search Adapter。

    使用火山方舟 Responses API + web_search。

    原生搜索失败时直接返回失败，不进入 Tavily 兜底。
    """

    model_name = "Doubao-Pro"
    provider = "volcengine"

    def __init__(self) -> None:
        self.config = get_model_config("Doubao-Pro")

        if not self.config.api_key:
            raise RuntimeError(
                "Doubao API key is missing."
            )

        self.client = OpenAI(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            timeout=90.0,
            max_retries=1,
        )

    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        allow_no_search: bool = False,
    ) -> Iterator[tuple[str, Any]]:
        """
        Doubao Responses API + Web Search 真流式输出。

        Yields:
            ("delta", text)
            ("complete", NativeSearchResponse)
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
                    should_fallback=False,
                ),
            )
            return

        try:
            input_messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "Perform live web research for the current user request. "
                        "The upstream search-decision system has already "
                        "determined that this request requires current web data. "
                        "You MUST use the web_search tool before answering. "
                        "Base the final answer on the retrieved web information. "
                        "Prefer current, reliable, primary and authoritative "
                        "sources when available. Conversation history is context, "
                        "not verified facts."
                    ),
                }
            ]

            history: list[dict[str, Any]] = []

            if messages:
                history = messages[-8:]

                # app.py 可能已经把当前 user turn 放进 messages，避免重复。
                if history:
                    last = history[-1]
                    last_role = last.get("role")
                    last_content = last.get("content")

                    if (
                        last_role == "user"
                        and isinstance(last_content, str)
                        and last_content.strip() == query
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

                   

                    input_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            print("⚡ Doubao Native Search streaming")
            print(
                "🧩 Doubao Native Search context turns:",
                len(input_messages) - 2,
            )

            stream = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                    }
                ],
                stream=True,
            )

            answer_parts: list[str] = []
            final_response = None

            for event in stream:
                event_type = (
                    getattr(event, "type", "")
                    or ""
                )

                if event_type == "response.output_text.delta":
                    delta = (
                        getattr(event, "delta", "")
                        or ""
                    )

                    if delta:
                        answer_parts.append(delta)
                        yield ("delta", delta)

                    continue

                if event_type == "response.completed":
                    final_response = getattr(
                        event,
                        "response",
                        None,
                    )

            answer = "".join(answer_parts).strip()

            used_web_search = False
            native_results: list[NativeSearchResult] = []
            seen_urls: set[str] = set()

            output_items = (
                getattr(
                    final_response,
                    "output",
                    None,
                )
                or []
            )

            # 检测 Web Search tool call + 提取来源
            for item in output_items:
                item_type = (
                    getattr(item, "type", "")
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

                if item_type not in {
                    "web_search_call",
                    "web_search",
                }:
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
                        getattr(source, "url", "")
                        or ""
                    ).strip()

                    title = (
                        getattr(source, "title", "")
                        or ""
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
                            source="Doubao Web Search",
                        )
                    )

            # 从最终文本 annotations 再提取引用
            for item in output_items:
                if getattr(item, "type", "") != "message":
                    continue

                contents = (
                    getattr(item, "content", None)
                    or []
                )

                for content_item in contents:
                    if (
                        getattr(content_item, "type", "")
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
                            getattr(annotation, "url", "")
                            or ""
                        ).strip()

                        title = (
                            getattr(annotation, "title", "")
                            or ""
                        ).strip()

                        if not url:
                            continue

                        used_web_search = True

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
                                source="Doubao Web Search",
                            )
                        )

            native_results = native_results[:max_results]

            print(
                "🔎 Doubao native stream:",
                {
                    "web_search": used_web_search,
                    "sources": len(native_results),
                },
            )

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
                            "Doubao native web search "
                            "produced no final answer."
                        ),
                        should_fallback=False,
                    ),
                )
                return

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
                        error=(
                            "Doubao returned without using "
                            "the native web search tool."
                        ),
                        should_fallback=False,
                    ),
                )
                return

            print(
                f"✅ Doubao native streaming search succeeded: "
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
            print(
                "❌ Doubao native streaming failed:",
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
            input_messages: list[dict[str, Any]] = []

            # ==================================================
            # 唯一 system message
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
            # 只保留 user + assistant
            # ==================================================
            if messages:
                for message in messages[-24:]:
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

                   

                    input_messages.append(
                        {
                            "role": role,
                            "content": content,
                        }
                    )

            # ==================================================
            # 当前搜索问题
            # ==================================================
            input_messages.append(
                {
                    "role": "user",
                    "content": query,
                }
            )

            # ==================================================
            # Doubao Responses API + Web Search
            # ==================================================
            response = self.client.responses.create(
                model=self.config.model_id,
                input=input_messages,
                tools=[
                    {
                        "type": "web_search",
                    }
                ],
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
            # 检测 Web Search tool call + 提取来源
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

                if item_type not in {
                    "web_search_call",
                    "web_search",
                }:
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
                            source="Doubao Web Search",
                        )
                    )

            # ==================================================
            # 从最终文本 annotations 再提取引用
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
                                source="Doubao Web Search",
                            )
                        )

            native_results = native_results[
                :max_results
            ]

            print(
                "🔎 Doubao native search:",
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
                        "Doubao returned without using "
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
                        "Doubao native web search "
                        "produced no final answer."
                    ),
                    should_fallback=True,
                )

            print(
                f"✅ Doubao native search succeeded: "
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
                "❌ Doubao native search failed:",
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