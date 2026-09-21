from __future__ import annotations

import json
from typing import Any, Iterator

import requests

from services.model_config import get_model_config
from services.native_search.base_native_search import (
    BaseNativeSearch, NativeSearchResponse, NativeSearchResult,
)


class DeepSeekNativeSearch(BaseNativeSearch):
    """DeepSeek official Anthropic-compatible server-side web search adapter."""

    model_name = "DeepSeek"
    provider = "deepseek"
    URL = "https://api.deepseek.com/anthropic/v1/messages"

    def __init__(self) -> None:
        self.config = get_model_config("DeepSeek")
        if not self.config.api_key:
            raise RuntimeError("DeepSeek API key is missing.")
        self.session = requests.Session()

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
            yield "complete", self._failure(query, "Empty search query.")
            return

        answer_parts: list[str] = []
        results: list[NativeSearchResult] = []
        seen_urls: set[str] = set()
        search_called = False
        finish_reason: str | None = None
        usage: dict[str, Any] | None = None
        error: str | None = None
        current_block_type = ""
        current_block_text = ""
        current_block_citations: list[Any] = []

        history: list[dict[str, Any]] = []
        for item in (messages or [])[-12:]:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role not in {"user", "assistant"} or not isinstance(content, str):
                continue
            if role == "user" and content.strip() == query:
                continue
            if content.strip():
                history.append({"role": role, "content": content[:3000]})

        payload = {
            "model": "deepseek-flash",
            "max_tokens": 15000,
            "stream": True,
            "tools": [{
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,
            }],
            "messages": history + [{"role": "user", "content": query}],
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        def add_source(source: Any) -> None:
            if not isinstance(source, dict):
                return
            url = source.get("url") or source.get("source_url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                return
            if url in seen_urls or len(results) >= max(1, max_results):
                return
            seen_urls.add(url)
            results.append(NativeSearchResult(
                title=str(source.get("title") or source.get("page_title") or ""),
                url=url,
                content=str(source.get("snippet") or source.get("content") or "")[:1200],
                source="DeepSeek Web Search",
            ))

        try:
            with self.session.post(
                self.URL, headers=headers, json=payload, stream=True,
                timeout=(10, 120),
            ) as response:
                response.raise_for_status()
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8", errors="replace")
                    if not raw_line.startswith("data: "):
                        continue
                    data = raw_line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    kind = event.get("type")
                    if kind == "error":
                        error = str(event.get("error") or "DeepSeek stream error")
                        break
                    if kind == "content_block_start":
                        block = event.get("content_block") or {}
                        current_block_type = block.get("type", "")
                        current_block_text = str(block.get("text") or "") if current_block_type == "text" else ""
                        current_block_citations = []
                        if current_block_type in {"server_tool_use", "web_search_tool_result"}:
                            search_called = True
                        if current_block_type == "web_search_tool_result":
                            content = block.get("content")
                            if isinstance(content, list):
                                for source in content:
                                    add_source(source)
                        if current_block_type == "text" and current_block_text:
                            answer_parts.append(current_block_text)
                            yield "delta", current_block_text
                    elif kind == "content_block_delta":
                        delta = event.get("delta") or {}
                        if current_block_type == "text" and delta.get("type") == "text_delta":
                            text = delta.get("text") or ""
                            if text:
                                answer_parts.append(text)
                                yield "delta", text
                        elif delta.get("type") == "citations_delta":
                            citation = delta.get("citation")
                            if citation:
                                current_block_citations.append(citation)
                    elif kind == "content_block_stop":
                        for citation in current_block_citations:
                            add_source(citation)
                        current_block_type = ""
                        current_block_text = ""
                        current_block_citations = []
                    elif kind == "message_delta":
                        delta = event.get("delta") or {}
                        finish_reason = delta.get("stop_reason") or finish_reason
                        if isinstance(event.get("usage"), dict):
                            usage = event["usage"]
                    elif kind == "message_start":
                        message = event.get("message") or {}
                        if isinstance(message.get("usage"), dict):
                            usage = message["usage"]
                    elif kind == "message_stop":
                        break
        except requests.RequestException as exc:
            error = f"DeepSeek native search request failed: {type(exc).__name__}: {exc}"
        except Exception as exc:
            error = f"DeepSeek native search stream failed: {type(exc).__name__}: {exc}"

        answer = "".join(answer_parts).strip()
        success = bool(answer and search_called and not error and finish_reason != "max_tokens")
        yield "complete", NativeSearchResponse(
            success=success,
            model_name=self.model_name,
            provider=self.provider,
            query=query,
            results=results,
            answer=answer,
            error=error or (None if success else "No complete searched answer returned."),
            should_fallback=not success,
            usage=usage,
        )

    def search(
        self,
        *,
        query: str,
        messages: list[dict[str, Any]] | None = None,
        max_results: int = 8,
    ) -> NativeSearchResponse:
        final: NativeSearchResponse | None = None
        for kind, value in self.stream_search(
            query=query, messages=messages, max_results=max_results,
        ):
            if kind == "complete":
                final = value
        return final or self._failure(query, "No final response returned.")

    def _failure(self, query: str, error: str) -> NativeSearchResponse:
        return NativeSearchResponse(
            success=False, model_name=self.model_name, provider=self.provider,
            query=query, error=error, should_fallback=True,
        )
