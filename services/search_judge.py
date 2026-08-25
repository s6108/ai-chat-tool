from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

from openai import OpenAI

from services.model_config import get_model_config


@dataclass(frozen=True)
class SearchJudgeDecision:
    need_search: bool
    search_type: str
    complexity: str
    raw_text: str
    elapsed_seconds: float


_ALLOWED_SEARCH_TYPES = {
    "none",
    "current_fact",
    "recent_event",
    "realtime_data",
    "general_web",
}

_ALLOWED_COMPLEXITIES = {
    "low",
    "medium",
    "high",
}


def _extract_json_object(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        raise ValueError(
            "Search Judge returned empty text."
        )

    # Accept plain JSON first.
    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # Tolerate fenced JSON or brief wrappers.
    match = re.search(
        r"\{.*\}",
        text,
        re.DOTALL,
    )

    if not match:
        raise ValueError(
            "Search Judge returned no JSON object."
        )

    parsed = json.loads(
        match.group(0)
    )

    if not isinstance(parsed, dict):
        raise ValueError(
            "Search Judge JSON is not an object."
        )

    return parsed


def judge_search_need(
    prompt: str,
    *,
    timeout_seconds: float = 8.0,
) -> SearchJudgeDecision:
    """
    Qwen-based semantic Search Judge for models that cannot
    reliably decide native-search use by themselves.

    Responsibilities are intentionally narrow:
    - decide whether fresh external information is required;
    - classify the external-information type;
    - estimate task complexity.

    It does NOT:
    - search the web;
    - generate search queries;
    - choose sources;
    - answer the user's question.
    """

    prompt = (prompt or "").strip()

    if not prompt:
        return SearchJudgeDecision(
            need_search=False,
            search_type="none",
            complexity="low",
            raw_text="",
            elapsed_seconds=0.0,
        )

    config = get_model_config(
        "Qwen"
    )

    if not config.api_key:
        raise RuntimeError(
            "Qwen API key is missing."
        )

    client = OpenAI(
        base_url=config.base_url,
        api_key=config.api_key,
        timeout=timeout_seconds,
        max_retries=0,
    )

    system_prompt = (
        "You are Megor's Search Judge. "
        "Judge only whether the user's CURRENT request requires "
        "fresh external information for an accurate answer. "
        "Work semantically in any language. Do not rely on a fixed "
        "Chinese or English keyword list. Do not answer the user. "
        "Return ONLY one JSON object with exactly these keys: "
        "need_search, search_type, complexity. "
        "need_search must be true or false. "
        "search_type must be one of: none, current_fact, recent_event, "
        "realtime_data, general_web. "
        "complexity must be one of: low, medium, high. "
        "Use current_fact for changing office-holders, current roles, "
        "current company leadership, current product/version/status, "
        "or other facts whose present value can change. "
        "Use realtime_data for weather, prices, markets, scores, "
        "exchange rates, schedules, or other live/current measurements. "
        "Use recent_event for news or events where recency is central. "
        "Use general_web when current external research is needed but "
        "the request is broader than a single current fact. "
        "Use none when stable knowledge, explanation, writing, math, "
        "coding, summarization, translation, or casual conversation "
        "can be answered accurately without fresh external information."
    )

    started = time.perf_counter()

    response = client.chat.completions.create(
        model=config.model_id,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0,
        max_tokens=80,
        extra_body={
            "enable_thinking": False,
        },
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    raw_text = (
        response
        .choices[0]
        .message
        .content
        or ""
    ).strip()

    payload = _extract_json_object(
        raw_text
    )

    need_search = bool(
        payload.get(
            "need_search",
            False,
        )
    )

    search_type = str(
        payload.get(
            "search_type",
            "none",
        )
        or "none"
    ).strip().lower()

    complexity = str(
        payload.get(
            "complexity",
            "low",
        )
        or "low"
    ).strip().lower()

    if search_type not in _ALLOWED_SEARCH_TYPES:
        raise ValueError(
            f"Invalid search_type: {search_type}"
        )

    if complexity not in _ALLOWED_COMPLEXITIES:
        raise ValueError(
            f"Invalid complexity: {complexity}"
        )

    if not need_search:
        search_type = "none"

    elif search_type == "none":
        search_type = "general_web"

    return SearchJudgeDecision(
        need_search=need_search,
        search_type=search_type,
        complexity=complexity,
        raw_text=raw_text,
        elapsed_seconds=elapsed,
    )
