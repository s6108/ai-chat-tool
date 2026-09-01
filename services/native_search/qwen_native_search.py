from __future__ import annotations

from typing import Any, Iterator

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

    原生搜索失败时直接返回失败状态，不进入 Tavily 兜底。
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

    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        allow_no_search: bool = False,
    ) -> Iterator[tuple[str, Any]]:
        """
        Qwen Responses API + Web Search 真流式输出。

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
                        "Answer the current user request accurately. "
                        "The upstream search-decision system has already "
                        "determined that this request requires current web data. "
                        "You MUST use the web_search tool before answering. "
                        "Base the final answer on the retrieved web information. "
                        "Prefer reliable and primary sources. "
                        "Treat prior assistant messages only as conversation "
                        "context, not as verified facts."
                    ),
                }
            ]

            # 保留少量历史上下文，不重复当前 query
            history = []

            if messages:
                history = messages[-24:]

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


            # ==========================================
            # Responses API 真流式
            # ==========================================
            stream = self.client.responses.create(
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
                stream=True,
            )

            answer_parts: list[str] = []
            final_response = None

            for event in stream:
                event_type = (
                    getattr(event, "type", "")
                    or ""
                )

                # 真正文本 delta
                if event_type == "response.output_text.delta":
                    delta = (
                        getattr(event, "delta", "")
                        or ""
                    )

                    if delta:
                        answer_parts.append(delta)
                        yield ("delta", delta)

                    continue

                # 最终完整 Response
                if event_type == "response.completed":
                    final_response = getattr(
                        event,
                        "response",
                        None,
                    )

            answer = "".join(answer_parts).strip()

            # ==========================================
            # 从最终 Response 提取搜索状态和来源
            # ==========================================
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
                            url.rstrip("/").casefold()
                        )

                        if normalized_url in seen_urls:
                            continue

                        seen_urls.add(normalized_url)

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Qwen Web Search",
                            )
                        )

            # 从最终 answer annotations 再提取引用
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
                            url.rstrip("/").casefold()
                        )

                        if normalized_url in seen_urls:
                            continue

                        seen_urls.add(normalized_url)

                        native_results.append(
                            NativeSearchResult(
                                title=title,
                                url=url,
                                source="Qwen Web Search",
                            )
                        )

            native_results = native_results[:max_results]


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
                            "Qwen native web search "
                            "produced no final answer."
                        ),
                        should_fallback=False,
                    ),
                )
                return

            # 中国模型在进入这里之前，
            # 已经由 Qwen 判断过是否需要联网。
            # 因此这里不再做 Tavily fallback。

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
                "❌ Qwen native streaming failed:",
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
            input_messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "Perform a live web search before answering the current user request. "
                        "The upstream routing layer has already determined that current or "
                        "externally verifiable information is required. "
                        "You must use the available web_search tool before producing the answer. "
                        "Do not answer only from internal model knowledge. "
                        "Prefer reliable and primary sources."
                    ),
                }
            ]

            # Keep only a small amount of conversational context.
            # Do not duplicate the current user query.
            history = []

            if messages:
                history = messages[-4:]

                # app.py commonly passes the current user turn as the
                # final history item. Remove it here because `query`
                # is appended exactly once below.
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


            # ==================================================
            # 安全判断
            # ==================================================
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