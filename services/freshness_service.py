from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from services.model_config import get_model_config


_QWEN_JUDGE_CLIENT = None
_QWEN_JUDGE_CLIENT_KEY = None


def _get_qwen_judge_client(config):
    """Reuse one Qwen Judge client and its HTTP connection pool."""
    global _QWEN_JUDGE_CLIENT, _QWEN_JUDGE_CLIENT_KEY

    client_key = (
        config.api_key,
        config.base_url,
    )

    if (
        _QWEN_JUDGE_CLIENT is None
        or _QWEN_JUDGE_CLIENT_KEY != client_key
    ):
        _QWEN_JUDGE_CLIENT = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=8.0,
            max_retries=0,
        )
        _QWEN_JUDGE_CLIENT_KEY = client_key

    return _QWEN_JUDGE_CLIENT



@dataclass(frozen=True)
class FreshnessDecision:
    need_search: bool
    confidence: float
    search_type: str
    reason: str



def _extract_json(text: str) -> dict:
    """
    Extract a JSON object from model output.

    Normal path is strict JSON. This helper also tolerates fenced JSON
    and surrounding prose without triggering a second model call.
    """
    text = (text or "").strip()

    if not text:
        raise ValueError(
            "Freshness judge returned empty text."
        )

    try:
        return json.loads(text)
    except Exception:
        pass

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    ).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(
        r"\{.*?\}",
        cleaned,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "No JSON object found in freshness response."
        )

    return json.loads(match.group(0))


def _parse_freshness_output(text: str) -> dict:
    """
    Parse the Qwen judge response without making another API call.

    Qwen is instructed to return JSON, but an OpenAI-compatible endpoint can
    occasionally return a short non-JSON form. In that case, recover the two
    fields locally instead of defaulting every parse anomaly to web search.
    """
    raw = (text or "").strip()

    if not raw:
        raise ValueError(
            "Freshness judge returned empty text."
        )

    try:
        return _extract_json(raw)
    except Exception:
        pass

    lowered = raw.casefold()

    # Recover need_search from common compact forms such as:
    # need_search=true
    # "need_search": true
    # search: yes/no
    need_match = re.search(
        r"(?:need[_\s-]*search|search)"
        r"\s*[:=]\s*"
        r"(true|false|yes|no|1|0)",
        lowered,
    )

    need_search = None

    if need_match:
        token = need_match.group(1)
        need_search = token in {
            "true",
            "yes",
            "1",
        }
    elif lowered in {
        "true",
        "yes",
        "search",
        "web",
    }:
        need_search = True
    elif lowered in {
        "false",
        "no",
        "none",
        "no_search",
        "no search",
    }:
        need_search = False

    type_match = re.search(
        r"(?:search[_\s-]*type|type)"
        r"\s*[:=]\s*"
        r"[\"']?"
        r"(none|current_fact|recent_event|realtime_data|general_web)"
        r"[\"']?",
        lowered,
    )

    search_type = (
        type_match.group(1)
        if type_match
        else None
    )

    if need_search is None and search_type is not None:
        need_search = search_type != "none"

    if need_search is None:
        raise ValueError(
            "Could not recover freshness fields from response."
        )

    if search_type is None:
        search_type = (
            "general_web"
            if need_search
            else "none"
        )

    return {
        "need_search": need_search,
        "search_type": search_type,
    }


@lru_cache(maxsize=512)
def judge_freshness(
    user_query: str,
) -> FreshnessDecision:
    """
    Qwen-based semantic freshness judge.

    Speed/safety principles:
    - one semantic judge call only;
    - Qwen thinking disabled;
    - short JSON-only response;
    - same-query LRU cache retained;
    - failure still defaults to web search.
    """

    query = (user_query or "").strip()

    if not query:
        return FreshnessDecision(
            need_search=False,
            confidence=1.0,
            search_type="none",
            reason="empty query",
        )

    try:
        config = get_model_config("Qwen")

        if not config.api_key:
            raise RuntimeError(
                "Qwen API key is unavailable."
            )

        client = _get_qwen_judge_client(config)

        system_prompt = (
            "Decide whether the CURRENT user request needs fresh web data. "
            "Understand the request semantically in any language. "
            "Do not answer the user. Return exactly one JSON object and nothing else. "
            "Schema: {\"need_search\":true|false,"
            "\"search_type\":\"none|current_fact|recent_event|realtime_data|general_web\"}. "
            "Use search for changing current facts, recent events, weather, prices, "
            "markets, scores, exchange rates, schedules, current roles, current "
            "product/version/status, or broader current web research. "
            "Use none for stable knowledge, explanation, writing, math, coding, "
            "summarization, translation, or casual conversation. "
            "If stale knowledge could materially mislead the answer, search."
        )

        response = client.chat.completions.create(
            model=config.model_id,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            temperature=0,
            max_tokens=48,
            extra_body={
                "enable_thinking": False,
            },
        )

        if not response.choices:
            raise ValueError(
                "Freshness judge returned no choices."
            )

        raw_text = (
            response
            .choices[0]
            .message
            .content
            or ""
        )

        data = _parse_freshness_output(raw_text)

        need_search_raw = data.get(
            "need_search",
            True,
        )

        if isinstance(need_search_raw, bool):
            need_search = need_search_raw
        elif isinstance(need_search_raw, str):
            need_search = (
                need_search_raw.strip().lower()
                == "true"
            )
        else:
            need_search = bool(need_search_raw)

        search_type = str(
            data.get(
                "search_type",
                "general_web"
                if need_search
                else "none",
            )
            or (
                "general_web"
                if need_search
                else "none"
            )
        ).strip().lower()

        allowed_search_types = {
            "none",
            "current_fact",
            "recent_event",
            "realtime_data",
            "general_web",
        }

        if search_type not in allowed_search_types:
            search_type = (
                "general_web"
                if need_search
                else "none"
            )

        if not need_search:
            search_type = "none"
        elif search_type == "none":
            search_type = "general_web"

        # Keep the existing FreshnessDecision contract for callers,
        # but do not spend model output tokens generating these debug fields.
        confidence = 0.95
        reason = "Qwen freshness judge"

        return FreshnessDecision(
            need_search=need_search,
            confidence=confidence,
            search_type=search_type,
            reason=reason,
        )

    except Exception as exc:
        print(
            "Freshness judge failed; defaulting to web search:",
            repr(exc),
        )

        return FreshnessDecision(
            need_search=True,
            confidence=0.0,
            search_type="general_web",
            reason=(
                "AI freshness judgement failed; "
                "defaulted to web search"
            ),
        )
