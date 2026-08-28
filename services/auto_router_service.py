from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from openai import OpenAI

from services.model_config import get_model_config


_QWEN_AUTO_ROUTER_CLIENT = None
_QWEN_AUTO_ROUTER_CLIENT_KEY = None

AUTO_TASK_TYPES = {
    "general",
    "coding_math",
    "news",
    "research",
    "vision",
}

AUTO_MODEL_MAP = {
    "general": "Qwen",
    "coding_math": "DeepSeek",
    "news": "Grok",
    "research": "Gemini",
    "vision": "GLM",
}


@dataclass(frozen=True)
class AutoRouteDecision:
    task_type: str
    model: str


def _get_qwen_auto_router_client(config):
    global _QWEN_AUTO_ROUTER_CLIENT, _QWEN_AUTO_ROUTER_CLIENT_KEY

    client_key = (config.api_key, config.base_url)

    if (
        _QWEN_AUTO_ROUTER_CLIENT is None
        or _QWEN_AUTO_ROUTER_CLIENT_KEY != client_key
    ):
        _QWEN_AUTO_ROUTER_CLIENT = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=5.0,
            max_retries=0,
        )
        _QWEN_AUTO_ROUTER_CLIENT_KEY = client_key

    return _QWEN_AUTO_ROUTER_CLIENT


def _extract_json(text: str) -> dict:
    text = (text or "").strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    cleaned = re.sub(
        r"^```(?:json)?\\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\\s*```$",
        "",
        cleaned,
    ).strip()

    try:
        return json.loads(cleaned)
    except Exception:
        pass

    match = re.search(r"\\{.*\\}", cleaned, flags=re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in Auto Router response.")

    return json.loads(match.group(0))


@lru_cache(maxsize=512)
def classify_auto_task(user_query: str) -> AutoRouteDecision:
    """Qwen semantic classifier used only by Auto Mode."""
    query = (user_query or "").strip()

    if not query:
        return AutoRouteDecision("general", "Qwen")

    try:
        config = get_model_config("Qwen")

        if not config.api_key:
            raise RuntimeError("Qwen API key is unavailable.")

        client = _get_qwen_auto_router_client(config)

        system_prompt = (
            "Classify the user's CURRENT request semantically in any language. "
            "Return JSON only with exactly one key: task_type. "
            "Choose exactly one: general, coding_math, news, research. "
            "general = everyday questions, writing, translation, summaries, "
            "general knowledge, business analysis, strategy and decision support, "
            "plus factual/query-style market requests such as stocks, securities, "
            "futures, indexes, exchange rates and commodity prices. "
            "coding_math = programming, debugging, software engineering, mathematics, "
            "calculations, algorithms and technical implementation. "
            "news = news, politics, international affairs, current events and recent developments. "
            "research = frontier science and technology, academic research, top-tier papers, "
            "scientific research, law, and deep financial research or analysis such as valuation, "
            "financial-statement analysis and macro-financial study. "
            "Simple market-price/data queries belong to general, not research. "
            "Do not answer. Do not decide whether web search is needed. Do not explain."
        )

        response = client.chat.completions.create(
            model=config.model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=16,
            extra_body={"enable_thinking": False},
        )

        if not response.choices:
            raise ValueError("Auto Router returned no choices.")

        data = _extract_json(response.choices[0].message.content or "")
        task_type = str(
            data.get("task_type", "general") or "general"
        ).strip().lower()

        if task_type not in AUTO_TASK_TYPES:
            task_type = "general"

        return AutoRouteDecision(
            task_type,
            AUTO_MODEL_MAP[task_type],
        )

    except Exception as exc:
        print("Auto Router failed; defaulting to Qwen:", repr(exc))
        return AutoRouteDecision("general", "Qwen")


def route_auto_model(
    user_query: str,
    *,
    has_image: bool = False,
) -> AutoRouteDecision:
    if has_image:
        return AutoRouteDecision("vision", "GLM")

    return classify_auto_task(user_query)
