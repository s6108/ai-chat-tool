from __future__ import annotations

from typing import Any

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

    原生搜索失败时，由 Megor 上层进入 Tavily Safety Net。
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

            # ==================================================
            # TEMP DIAGNOSTIC: inspect the REAL Doubao Responses payload
            # Read-only: does not change search / fallback behaviour.
            # ==================================================
            try:
                print("\n🧪 [DOUBAO RAW] response_type =", type(response).__name__)

                if hasattr(response, "model_dump"):
                    raw_response = response.model_dump()
                    print("🧪 [DOUBAO RAW] top_keys =", list(raw_response.keys()))

                    raw_output = raw_response.get("output") or []
                    print("🧪 [DOUBAO RAW] output_count =", len(raw_output))

                    for idx, raw_item in enumerate(raw_output):
                        if not isinstance(raw_item, dict):
                            print(
                                f"🧪 [DOUBAO RAW] output[{idx}] python_type =",
                                type(raw_item).__name__,
                            )
                            continue

                        print(
                            f"🧪 [DOUBAO RAW] output[{idx}].type =",
                            raw_item.get("type"),
                        )
                        print(
                            f"🧪 [DOUBAO RAW] output[{idx}].keys =",
                            list(raw_item.keys()),
                        )

                        action = raw_item.get("action")
                        if isinstance(action, dict):
                            print(
                                f"🧪 [DOUBAO RAW] output[{idx}].action.keys =",
                                list(action.keys()),
                            )
                            action_sources = action.get("sources") or []
                            print(
                                f"🧪 [DOUBAO RAW] output[{idx}].action.sources_count =",
                                len(action_sources),
                            )
                            if action_sources and isinstance(action_sources[0], dict):
                                print(
                                    f"🧪 [DOUBAO RAW] output[{idx}].action.sources[0].keys =",
                                    list(action_sources[0].keys()),
                                )

                        contents = raw_item.get("content") or []
                        if isinstance(contents, list):
                            print(
                                f"🧪 [DOUBAO RAW] output[{idx}].content_count =",
                                len(contents),
                            )
                            for cidx, raw_content in enumerate(contents):
                                if not isinstance(raw_content, dict):
                                    continue
                                print(
                                    f"🧪 [DOUBAO RAW] output[{idx}].content[{cidx}].type =",
                                    raw_content.get("type"),
                                )
                                annotations = raw_content.get("annotations") or []
                                print(
                                    f"🧪 [DOUBAO RAW] output[{idx}].content[{cidx}].annotations_count =",
                                    len(annotations),
                                )
                                if annotations and isinstance(annotations[0], dict):
                                    print(
                                        f"🧪 [DOUBAO RAW] annotation[0].keys =",
                                        list(annotations[0].keys()),
                                    )

                    usage = raw_response.get("usage")
                    if isinstance(usage, dict):
                        print("🧪 [DOUBAO RAW] usage.keys =", list(usage.keys()))
                else:
                    print(
                        "🧪 [DOUBAO RAW] attrs =",
                        [name for name in dir(response) if not name.startswith("_")][:80],
                    )

            except Exception as diagnostic_error:
                print(
                    "⚠️ [DOUBAO RAW] diagnostic failed:",
                    repr(diagnostic_error),
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