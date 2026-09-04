from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx
from openai import OpenAI

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch,
    NativeSearchResponse,
)


class KimiNativeSearch(BaseNativeSearch):
    """
    Kimi 原生联网搜索 Adapter（Formula API 版）。

    2026-08 起 Moonshot 官方建议新集成使用：
        moonshot/web-search:latest

    不再使用旧的 builtin_function.$web_search。

    流程：
    1. GET /formulas/moonshot/web-search:latest/tools
       获取标准 function tool schema
    2. 让 Kimi 通过 chat.completions 正常发起 tool_call
    3. POST /formulas/moonshot/web-search:latest/fibers
       由 Moonshot 服务端真正执行搜索
    4. 将 context.encrypted_output / context.output
       作为 role=tool 原样回传给 Kimi
    5. Kimi 基于真实搜索结果继续回答；支持多轮搜索
    """

    model_name = "Kimi"
    provider = "moonshot"

    FORMULA_URI = "moonshot/web-search:latest"

    def __init__(self) -> None:
        self.config = get_model_config("Kimi")

        if not self.config.api_key:
            raise RuntimeError("Kimi API key is missing.")

        self.base_url = self.config.base_url.rstrip("/")

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.config.api_key,
            timeout=90.0,
            max_retries=1,
        )

        self.http = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            timeout=90.0,
        )

        self.formula_tools = self._load_formula_tools()

    # ==================================================
    # Formula 工具声明
    # ==================================================
    def _load_formula_tools(self) -> list[dict[str, Any]]:
        response = self.http.get(
            f"/formulas/{self.FORMULA_URI}/tools"
        )
        response.raise_for_status()

        payload = response.json()
        tools = payload.get("tools")

        if not isinstance(tools, list) or not tools:
            raise RuntimeError(
                "Kimi Formula web-search returned no tool definitions."
            )

        print(
            "✅ Kimi Formula tools loaded:",
            [
                (
                    tool.get("function", {})
                    .get("name")
                    if isinstance(tool, dict)
                    else None
                )
                for tool in tools
            ],
        )

        return tools

    # ==================================================
    # 对话上下文
    # ==================================================
    def _build_messages(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        # 每一轮都动态注入真实当前 UTC 时间，禁止模型依赖训练期日期。
        now_utc = datetime.now(timezone.utc)
        current_utc = now_utc.isoformat(timespec="seconds")

        kimi_messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are Kimi performing live web research for the "
                    "current user request. The upstream search-decision "
                    "system has already determined that fresh web "
                    "information is required. You MUST use the provided "
                    "web_search tool before answering. For normal factual "
                    "or real-time questions, use web_search exactly once, "
                    "then answer directly from that result. Do not search "
                    "again merely to confirm the same fact. "
                    "Base the final answer on the retrieved web results. "
                    f"The actual current UTC datetime is {current_utc}. "
                    "For relative date words such as today, tomorrow, "
                    "yesterday, this week, or currently, resolve the exact "
                    "calendar date using the target location's local timezone. "
                    "Never infer the current date from model memory or from "
                    "old webpages. For weather, news, prices, office holders "
                    "and other time-sensitive requests, include the resolved "
                    "calendar date in the web-search query whenever useful. "
                    "Reject stale search results whose dates do not match the "
                    "resolved request date. Prefer current, reliable, primary "
                    "and authoritative sources. Conversation history is "
                    "context only and must not replace fresh search results."
                ),
            }
        ]

        if messages:
            history = messages[-8:]

            # app.py 往往已经把当前 user turn 放在最后，
            # 避免与下面 query 重复。
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

                # 搜索阶段只保留用户历史，避免上一模型的失败回答
                # 污染当前搜索。
                if role != "user":
                    continue

                if not isinstance(content, str):
                    continue

                content = content.strip()
                if not content:
                    continue

                if len(content) > 1500:
                    content = content[:1500]

                kimi_messages.append(
                    {
                        "role": "user",
                        "content": content,
                    }
                )

        kimi_messages.append(
            {
                "role": "user",
                "content": (
                    "[TIME_GROUNDING]\n"
                    f"Actual current UTC datetime: {current_utc}.\n"
                    "Resolve relative dates using the target location's local "
                    "timezone before searching. For time-sensitive requests, "
                    "prefer results that explicitly match the resolved date.\n"
                    "[/TIME_GROUNDING]\n\n"
                    f"{query}"
                ),
            }
        )

        return kimi_messages

    # ==================================================
    # 执行 Formula Fiber
    # ==================================================
    def _execute_formula_tool(
        self,
        *,
        tool_name: str,
        raw_arguments: str,
    ) -> str:
        response = self.http.post(
            f"/formulas/{self.FORMULA_URI}/fibers",
            json={
                "name": tool_name,
                "arguments": raw_arguments,
            },
        )
        response.raise_for_status()

        payload = response.json()
        status = payload.get("status")

        if status != "succeeded":
            raise RuntimeError(
                "Kimi Formula web-search failed: "
                f"status={status!r}, payload={payload!r}"
            )

        context = payload.get("context") or {}

        if not isinstance(context, dict):
            raise RuntimeError(
                "Kimi Formula web-search returned invalid context."
            )

        # web-search 是 protected Formula，官方文档说明主要返回
        # encrypted_output；普通 Formula 可能返回 output。
        tool_output = (
            context.get("encrypted_output")
            or context.get("output")
        )

        if not isinstance(tool_output, str) or not tool_output.strip():
            raise RuntimeError(
                "Kimi Formula web-search returned no tool output."
            )

        print(
            "🌐 Kimi Formula web-search succeeded:",
            {
                "fiber_id": payload.get("id"),
                "status": status,
                "output_chars": len(tool_output),
            },
        )

        return tool_output

    # ==================================================
    # Formula schema helper
    # ==================================================
    def _get_web_search_tool_name(self) -> str:
        for tool in self.formula_tools:
            if not isinstance(tool, dict):
                continue
            function = tool.get("function") or {}
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()

        return "web_search"

    def _supports_direct_query_argument(self) -> bool:
        """
        Formula 当前 web-search schema 通常暴露 query 参数。
        若 schema 明确包含 query，就允许跳过第一次 Kimi tool-selection。
        """
        for tool in self.formula_tools:
            if not isinstance(tool, dict):
                continue

            function = tool.get("function") or {}
            if not isinstance(function, dict):
                continue

            parameters = function.get("parameters") or {}
            if not isinstance(parameters, dict):
                continue

            properties = parameters.get("properties") or {}
            if (
                isinstance(properties, dict)
                and "query" in properties
            ):
                return True

        return False

    def _stream_final_answer(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
    ) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=2500,
            temperature=1,
            stream=True,
        )

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)

            if isinstance(content, str) and content:
                yield content

    # ==================================================
    # 真流式 Formula Search
    # ==================================================
    def stream_search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
        allow_no_search: bool = False,
    ) -> Iterator[tuple[str, Any]]:
        del max_results, allow_no_search

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
            kimi_messages = self._build_messages(
                query=query,
                messages=messages,
            )

            search_model_id = (
                getattr(self.config, "search_model_id", None)
                or self.config.model_id
            )

            print("⚡ Kimi Formula Native Search streaming")
            print("🧠 Kimi search model:", search_model_id)
            print(
                "🧩 Kimi Native Search context turns:",
                len(kimi_messages) - 2,
            )

            used_web_search = False
            final_answer_parts: list[str] = []

            # ==================================================
            # FAST PATH
            # Megor 上游已经判定必须联网，并且 resolved_search_prompt
            # 已经是可搜索问题。若 Formula schema 支持 query 参数，
            # 直接执行 Formula，省掉第一次 Kimi tool-selection 调用。
            # ==================================================
            if self._supports_direct_query_argument():
                try:
                    tool_name = self._get_web_search_tool_name()
                    raw_arguments = json.dumps(
                        {"query": query},
                        ensure_ascii=False,
                    )

                    print(
                        "🚀 Kimi Formula direct-search fast path:",
                        raw_arguments,
                    )

                    tool_output = self._execute_formula_tool(
                        tool_name=tool_name,
                        raw_arguments=raw_arguments,
                    )

                    used_web_search = True

                    synthetic_tool_call_id = (
                        "call_" + uuid.uuid4().hex[:24]
                    )

                    kimi_messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": synthetic_tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": raw_arguments,
                                    },
                                }
                            ],
                        }
                    )

                    kimi_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": synthetic_tool_call_id,
                            "name": tool_name,
                            "content": tool_output,
                        }
                    )

                    # 强制最终回答，不允许再次发起搜索。
                    kimi_messages.append(
                        {
                            "role": "system",
                            "content": (
                                "The web search has already been completed. "
                                "Do not call any tool again. Answer the user's "
                                "question directly from the retrieved result. "
                                "For time-sensitive facts, use only information "
                                "matching the resolved current date."
                            ),
                        }
                    )

                    for text in self._stream_final_answer(
                        model_id=search_model_id,
                        messages=kimi_messages,
                    ):
                        final_answer_parts.append(text)
                        yield ("delta", text)

                    final_answer = "".join(
                        final_answer_parts
                    ).strip()

                    print(
                        "🔎 Kimi Formula fast stream:",
                        {
                            "web_search": True,
                            "answer_chars": len(final_answer),
                        },
                    )

                    if final_answer:
                        print(
                            "✅ Kimi Formula direct-search fast path succeeded"
                        )
                        yield (
                            "complete",
                            NativeSearchResponse(
                                success=True,
                                model_name=self.model_name,
                                provider=self.provider,
                                query=query,
                                results=[],
                                answer=final_answer,
                                should_fallback=False,
                            ),
                        )
                        return

                    raise RuntimeError(
                        "Kimi fast path produced no final answer."
                    )

                except Exception as fast_error:
                    print(
                        "⚠️ Kimi Formula fast path failed; "
                        "falling back to tool-selection flow:",
                        repr(fast_error),
                    )

                    # Reset answer accumulator before fallback.
                    final_answer_parts = []

            # ==================================================
            # SAFE FALLBACK
            # 保留已经验证成功的原 Formula tool-selection 流程。
            # ==================================================
            max_rounds = 2

            for round_index in range(1, max_rounds + 1):
                stream = self.client.chat.completions.create(
                    model=search_model_id,
                    messages=kimi_messages,
                    tools=self.formula_tools,
                    max_tokens=4000,
                    temperature=1,
                    stream=True,
                )

                round_content_parts: list[str] = []

                # OpenAI-compatible streaming tool_call delta 聚合
                tool_calls_by_index: dict[int, dict[str, Any]] = {}
                finish_reason: str | None = None

                for chunk in stream:
                    if not chunk.choices:
                        continue

                    choice = chunk.choices[0]
                    finish_reason = (
                        choice.finish_reason
                        or finish_reason
                    )

                    delta = choice.delta

                    content = getattr(delta, "content", None)
                    if isinstance(content, str) and content:
                        round_content_parts.append(content)

                    delta_tool_calls = (
                        getattr(delta, "tool_calls", None)
                        or []
                    )

                    for delta_tool_call in delta_tool_calls:
                        index = (
                            getattr(delta_tool_call, "index", None)
                        )
                        if index is None:
                            index = 0

                        state = tool_calls_by_index.setdefault(
                            index,
                            {
                                "id": "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": "",
                                },
                            },
                        )

                        tool_call_id = getattr(
                            delta_tool_call,
                            "id",
                            None,
                        )
                        if tool_call_id:
                            state["id"] = tool_call_id

                        function = getattr(
                            delta_tool_call,
                            "function",
                            None,
                        )
                        if function is not None:
                            name = getattr(
                                function,
                                "name",
                                None,
                            )
                            arguments = getattr(
                                function,
                                "arguments",
                                None,
                            )

                            if name:
                                state["function"]["name"] += name

                            if arguments:
                                state["function"]["arguments"] += arguments

                # ----------------------------------------------
                # Kimi 请求工具
                # ----------------------------------------------
                if tool_calls_by_index:
                    # Fast path: one Formula search is enough for ordinary
                    # factual/realtime queries. If Kimi asks to search again,
                    # force a final answer from the result already retrieved.
                    if used_web_search:
                        kimi_messages.append(
                            {
                                "role": "system",
                                "content": (
                                    "Do not call web_search again. Answer the "
                                    "user directly using the web-search result "
                                    "already present in the conversation."
                                ),
                            }
                        )
                        final_stream = self.client.chat.completions.create(
                            model=search_model_id,
                            messages=kimi_messages,
                            max_tokens=4000,
                            temperature=1,
                            stream=True,
                        )
                        for final_chunk in final_stream:
                            if not final_chunk.choices:
                                continue
                            final_text = getattr(
                                final_chunk.choices[0].delta,
                                "content",
                                None,
                            )
                            if isinstance(final_text, str) and final_text:
                                final_answer_parts.append(final_text)
                                yield ("delta", final_text)
                        break

                    tool_calls = [
                        tool_calls_by_index[index]
                        for index in sorted(tool_calls_by_index)
                    ]

                    kimi_messages.append(
                        {
                            "role": "assistant",
                            "content": (
                                "".join(round_content_parts)
                                or None
                            ),
                            "tool_calls": tool_calls,
                        }
                    )

                    for tool_call in tool_calls:
                        tool_name = (
                            tool_call["function"]["name"]
                        )
                        raw_arguments = (
                            tool_call["function"]["arguments"]
                            or "{}"
                        )

                        if tool_name != "web_search":
                            raise RuntimeError(
                                "Unexpected Kimi Formula tool: "
                                f"{tool_name}"
                            )

                        used_web_search = True

                        tool_output = self._execute_formula_tool(
                            tool_name=tool_name,
                            raw_arguments=raw_arguments,
                        )

                        kimi_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": tool_output,
                            }
                        )

                    # 允许 Kimi 根据搜索结果再次细化查询
                    continue

                # ----------------------------------------------
                # 没有 tool_calls：这是最终回答
                # ----------------------------------------------
                if round_content_parts:
                    for text in round_content_parts:
                        final_answer_parts.append(text)
                        yield ("delta", text)

                break

            final_answer = "".join(
                final_answer_parts
            ).strip()

            print(
                "🔎 Kimi Formula native stream:",
                {
                    "web_search": used_web_search,
                    "answer_chars": len(final_answer),
                },
            )

            if not used_web_search:
                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        answer=final_answer,
                        error=(
                            "Kimi returned without using "
                            "Formula web_search."
                        ),
                        should_fallback=False,
                    ),
                )
                return

            if not final_answer:
                yield (
                    "complete",
                    NativeSearchResponse(
                        success=False,
                        model_name=self.model_name,
                        provider=self.provider,
                        query=query,
                        error=(
                            "Kimi Formula web-search produced "
                            "no final answer."
                        ),
                        should_fallback=False,
                    ),
                )
                return

            print("✅ Kimi Formula native search succeeded")

            yield (
                "complete",
                NativeSearchResponse(
                    success=True,
                    model_name=self.model_name,
                    provider=self.provider,
                    query=query,
                    results=[],
                    answer=final_answer,
                    should_fallback=False,
                ),
            )

        except Exception as error:
            print(
                "❌ Kimi Formula native streaming failed:",
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

    # ==================================================
    # 同步接口：复用 Formula 逻辑
    # ==================================================
    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
    ) -> NativeSearchResponse:
        answer_parts: list[str] = []
        final_response: NativeSearchResponse | None = None

        for event_kind, payload in self.stream_search(
            query=query,
            messages=messages,
            max_results=max_results,
        ):
            if event_kind == "delta":
                answer_parts.append(
                    payload
                    if isinstance(payload, str)
                    else str(payload or "")
                )
                continue

            if event_kind == "complete":
                final_response = payload

        if final_response is not None:
            return final_response

        return NativeSearchResponse(
            success=False,
            model_name=self.model_name,
            provider=self.provider,
            query=query,
            answer="".join(answer_parts).strip(),
            error="Kimi Formula native search returned no response.",
            should_fallback=True,
        )
