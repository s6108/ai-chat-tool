from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from services.model_config import get_model_config


@dataclass(frozen=True)
class FreshnessDecision:
    need_search: bool
    confidence: float
    search_type: str
    reason: str


SYSTEM_PROMPT = """
You are the web-search decision layer of an AI assistant.

Your ONLY task is to determine whether answering the user's question
reliably requires fresh information from the public web.

Do NOT answer the user's question.

Judge the MEANING and intent of the question.
Do NOT depend on keywords or any specific language.

Search should be used whenever the answer may have materially changed
since the model's training data.

Examples include, but are not limited to:

- current or recent events
- politics, governments, public officials, elections, wars or diplomacy
- laws, regulations, policies or official rules
- current company information, executives, financing or business status
- prices, financial markets, exchange rates or economic data
- weather, schedules, sports, travel or transportation
- currently available products, services, software, model versions or APIs
- current technology or AI developments
- recommendations whose quality depends on what exists now
- questions about who currently holds a role or position
- facts where an outdated answer could materially mislead the user


DO NOT search for stable, timeless knowledge when the answer does not
depend on the current state of the world.

Examples:

- What is Python?
- What is photosynthesis?
- Explain Newton's second law.
- What is a database?
- How does binary search work?
- Translate this sentence.
- Rewrite this paragraph.
- Solve a mathematics problem.
- Explain a stable historical or scientific concept.


The fact that newer sources may exist does NOT mean web search is required.

Ask yourself:

"If I answered this using well-established knowledge from several years
ago, could the answer now be materially wrong?"

If NO, do not search.

If YES, search.

If the question asks about a fact that can change over time — such as
who currently holds an office, who currently runs a company, a current
price, law, policy, product version, schedule, market condition, or
recent event — search.

For genuinely uncertain cases, prefer search.


Classify search_type as exactly one of:

- "none":
  No web search is needed.

- "current_fact":
  The user is asking for the current holder, current status, current
  version, current leadership, current rule, or another fact whose
  present-day value may differ from older information.

- "recent_event":
  The user is asking about recent news, developments, politics,
  announcements, events, or changes.

- "realtime_data":
  The answer depends on live or near-live data such as weather,
  markets, exchange rates, sports, schedules, or availability.

- "general_web":
  Web research would improve reliability or recommendations, but the
  answer is not specifically a live value or current office/status.


Return ONLY valid JSON.

The JSON must have exactly these fields:

{
  "need_search": true,
  "confidence": 0.95,
  "search_type": "current_fact",
  "reason": "The holder of this office can change over time."
}
"""


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
    使用轻量 AI 判断用户问题是否需要联网。

    设计原则：
    1. 不依赖关键词；
    2. 支持不同语言；
    3. 稳定知识尽量不联网；
    4. 可能过时的信息优先联网；
    5. 判断失败时默认联网；
    6. 同一个问题通过缓存只判断一次。
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
        config = get_model_config(
            "DeepSeek"
        )

        if not config.api_key:
            raise RuntimeError(
                "DeepSeek API key is unavailable."
            )

        client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=8.0,
        )

        request_params = {
            "model": config.model_id,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": query,
                },
            ],
            "temperature": 0,
        }

        if getattr(
            config,
            "uses_max_completion_tokens",
            False,
        ):
            request_params[
                "max_completion_tokens"
            ] = 160
        else:
            request_params[
                "max_tokens"
            ] = 160

        response = (
            client.chat.completions.create(
                **request_params
            )
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

        data = _extract_json(
            raw_text
        )

        need_search_raw = data.get(
            "need_search",
            True,
        )

        if isinstance(
            need_search_raw,
            bool,
        ):
            need_search = need_search_raw
        elif isinstance(
            need_search_raw,
            str,
        ):
            need_search = (
                need_search_raw
                .strip()
                .lower()
                == "true"
            )
        else:
            need_search = bool(
                need_search_raw
            )

        try:
            confidence = float(
                data.get(
                    "confidence",
                    0.5,
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = 0.5

        confidence = max(
            0.0,
            min(
                confidence,
                1.0,
            ),
        )

        search_type = str(
            data.get(
                "search_type",
                (
                    "general_web"
                    if need_search
                    else "none"
                ),
            )
        ).strip().lower()

        allowed_search_types = {
            "none",
            "current_fact",
            "recent_event",
            "realtime_data",
            "general_web",
        }

        if (
            search_type
            not in allowed_search_types
        ):
            search_type = (
                "general_web"
                if need_search
                else "none"
            )

        # 两个字段保持一致
        if not need_search:
            search_type = "none"

        elif search_type == "none":
            search_type = "general_web"

        reason = str(
            data.get(
                "reason",
                "",
            )
        ).strip()

        if not reason:
            reason = (
                "Search required."
                if need_search
                else "Stable knowledge."
            )

        decision = FreshnessDecision(
            need_search=need_search,
            confidence=confidence,
            search_type=search_type,
            reason=reason,
        )

        print(
            "AI FRESHNESS:",
            {
                "query": query,
                "need_search": (
                    decision.need_search
                ),
                "confidence": (
                    decision.confidence
                ),
                "search_type": (
                    decision.search_type
                ),
                "reason": (
                    decision.reason
                ),
            },
        )

        return decision

    except Exception as error:
        print(
            "Freshness judge failed; "
            "defaulting to web search:",
            repr(error),
        )

        # Fail open：
        # 判断器自身失败时宁愿联网，
        # 不允许直接依赖可能过时的模型记忆。
        return FreshnessDecision(
            need_search=True,
            confidence=0.0,
            search_type="general_web",
            reason=(
                "AI freshness judgement "
                "failed; defaulted to web search"
            ),
        )