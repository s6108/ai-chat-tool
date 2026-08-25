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
    从模型返回内容中提取 JSON。

    正常情况下模型应该只返回 JSON，
    这里保留容错，防止模型偶尔加 ```json 或其他文字。
    """

    text = (text or "").strip()

    if not text:
        raise ValueError(
            "Freshness judge returned empty text."
        )

    # 先直接尝试
    try:
        return json.loads(text)
    except Exception:
        pass

    # 去掉 ```json ... ```
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

    # 最后尝试提取第一个 JSON 对象
    match = re.search(
        r"\{.*\}",
        cleaned,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "No JSON object found in freshness response."
        )

    return json.loads(
        match.group(0)
    )


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
            "You are Megor's Search Judge. "
            "Judge only whether the user's CURRENT request requires "
            "fresh external information for an accurate answer. "
            "Work semantically in any language. Do not answer the user. "
            "Return ONLY one JSON object with exactly these keys: "
            "need_search, confidence, search_type, reason. "
            "Keep reason extremely short: at most 12 words. "
            "need_search must be true or false. "
            "confidence must be a number from 0 to 1. "
            "search_type must be one of: none, current_fact, recent_event, "
            "realtime_data, general_web. "
            "Use current_fact for changing office-holders, current roles, "
            "current company leadership, current product/version/status, "
            "or other facts whose present value can change. "
            "Use realtime_data for weather, prices, markets, scores, "
            "exchange rates, schedules, or other live measurements. "
            "Use recent_event for news or events where recency is central. "
            "Use general_web when current external research is needed but "
            "the request is broader than a single current fact. "
            "Use none when stable knowledge, explanation, writing, math, "
            "coding, summarization, translation, or casual conversation "
            "can be answered accurately without fresh external information. "
            "When genuinely uncertain whether stale knowledge could materially "
            "mislead the user, prefer search."
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
            max_tokens=64,
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

        data = _extract_json(raw_text)

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

        try:
            confidence = float(
                data.get("confidence", 0.95)
            )
        except (TypeError, ValueError):
            confidence = 0.95

        confidence = max(
            0.0,
            min(confidence, 1.0),
        )

        reason = str(
            data.get(
                "reason",
                "Qwen semantic freshness judgement.",
            )
            or "Qwen semantic freshness judgement."
        ).strip()

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
