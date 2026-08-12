from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

from openai import OpenAI

from services.date_service import get_search_query
from services.freshness_service import judge_freshness
from services.model_config import get_model_config


@dataclass(frozen=True)
class SearchPlan:
    queries: list[str]
    preferred_domains: list[str] = field(default_factory=list)


DOMAIN_PLANNER_PROMPT = """
You are the source-planning layer of a web search system.

The user is asking for a CURRENT FACT that may change over time.

Your task is NOT to answer the user's question.

Your task is to identify the most authoritative FIRST-PARTY domains
that are likely to contain the current official answer.

Examples of first-party authoritative sources:

- government office or government department websites
- official company websites
- official organization websites
- official product or developer documentation
- official university or institution websites

Prefer the organization that directly owns or controls the fact.

Examples:

Question:
Who is the current Prime Minister of Canada?

Preferred domains could include:
pm.gc.ca
canada.ca

Question:
Who is the CEO of Apple?

Preferred domain:
apple.com

Question:
What is the current Claude model?

Preferred domain:
anthropic.com

Question:
What is the latest Python version?

Preferred domains could include:
python.org

Do NOT return:
- Wikipedia
- Reddit
- social media
- news aggregators
- blogs
- SEO sites
- unofficial reference websites

Return ONLY valid JSON:

{
  "preferred_domains": [
    "example.gov",
    "example.com"
  ]
}

Return at most 4 domains.
If no clear first-party authoritative domain can be identified,
return an empty list.
"""


def _extract_json(text: str) -> dict:
    text = (text or "").strip()

    if not text:
        raise ValueError("Empty domain planner response.")

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
        r"\{.*\}",
        cleaned,
        flags=re.DOTALL,
    )

    if not match:
        raise ValueError(
            "No JSON object found in domain planner response."
        )

    return json.loads(match.group(0))


def _normalize_domain(domain: str) -> str:
    domain = (domain or "").strip().lower()

    domain = re.sub(
        r"^https?://",
        "",
        domain,
    )

    domain = domain.split("/")[0]

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


@lru_cache(maxsize=512)
def _plan_preferred_domains(
    user_query: str,
) -> tuple[str, ...]:
    """
    让 AI 根据问题语义选择第一方权威域名。

    判断失败时返回空列表。
    不影响后续普通搜索 fallback。
    """

    query = (user_query or "").strip()

    if not query:
        return ()

    try:
        config = get_model_config("DeepSeek")

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
                    "content": DOMAIN_PLANNER_PROMPT,
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
            ] = 120
        else:
            request_params[
                "max_tokens"
            ] = 120

        response = client.chat.completions.create(
            **request_params
        )

        if not response.choices:
            raise ValueError(
                "Domain planner returned no choices."
            )

        raw_text = (
            response
            .choices[0]
            .message
            .content
            or ""
        )

        data = _extract_json(raw_text)

        raw_domains = data.get(
            "preferred_domains",
            [],
        )

        if not isinstance(raw_domains, list):
            raw_domains = []

        domains: list[str] = []

        for item in raw_domains:
            domain = _normalize_domain(
                str(item)
            )

            if (
                domain
                and "." in domain
                and domain not in domains
            ):
                domains.append(domain)

            if len(domains) >= 4:
                break

        print(
            "AI PREFERRED DOMAINS:",
            query,
            domains,
        )

        return tuple(domains)

    except Exception as error:
        print(
            "Preferred-domain planning failed:",
            repr(error),
        )

        return ()

CONTEXT_RESOLVER_PROMPT = """
You rewrite the user's latest message into a standalone web-search question.

Use the recent conversation only to resolve:
- omitted subjects
- pronouns
- references such as "this", "that", "him", "her", "it"
- follow-up requests such as "search again", "check again", "what about now"

Rules:

1. Do NOT answer the question.
2. Do NOT invent or correct facts.
3. Preserve the user's actual intent.
4. Use prior conversation only to recover missing context.
5. If the latest user message is already a complete standalone question,
   return it unchanged.
6. Return ONLY the rewritten question.
"""


def resolve_search_query(
    prompt: str,
    messages: list[dict],
) -> str:
    """
    将依赖上下文的追问补全成可独立搜索的问题。

    例如：

    历史：
    User: 加拿大总理是谁？
    Assistant: 加拿大现任总理是 Mark Carney。

    当前：
    User: 你再搜索一下

    输出类似：
    重新搜索并核实加拿大现任总理是谁？
    """

    prompt = (prompt or "").strip()

    if not prompt:
        return ""

    # 只取最近几轮，避免上下文过长
    recent_messages = messages[-8:] if messages else []

    context_lines: list[str] = []

    for message in recent_messages:
        role = message.get("role")
        content = message.get("content")

        if role not in {"user", "assistant"}:
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if not content:
            continue

        # 避免把完整长回答全部交给 resolver
        if len(content) > 800:
            content = content[:800]

        context_lines.append(
            f"{role.upper()}: {content}"
        )

    context_text = "\n".join(context_lines)

    try:
        config = get_model_config("DeepSeek")

        if not config.api_key:
            return prompt

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
                    "content": CONTEXT_RESOLVER_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "Recent conversation:\n"
                        f"{context_text}\n\n"
                        "Latest user message:\n"
                        f"{prompt}\n\n"
                        "Standalone search question:"
                    ),
                },
            ],
            "temperature": 0,
        }

        if getattr(
            config,
            "uses_max_completion_tokens",
            False,
        ):
            request_params["max_completion_tokens"] = 160
        else:
            request_params["max_tokens"] = 160

        response = client.chat.completions.create(
            **request_params
        )

        if not response.choices:
            return prompt

        resolved = (
            response.choices[0]
            .message
            .content
            or ""
        ).strip()

        if not resolved:
            return prompt

        print(
            "🧩 SEARCH QUERY RESOLVED:",
            repr(prompt),
            "→",
            repr(resolved),
        )

        return resolved

    except Exception as error:
        print(
            "Search query resolver failed:",
            repr(error),
        )

        return prompt


def plan_search(prompt: str) -> SearchPlan:
    """
    根据 AI Freshness Layer 生成完整搜索计划。

    返回：
    - queries
    - preferred_domains
    """

    prompt = (prompt or "").strip()

    if not prompt:
        return SearchPlan(
            queries=[],
            preferred_domains=[],
        )

    decision = judge_freshness(prompt)

    today = date.today().isoformat()

    # ==================================================
    # CURRENT FACT
    # ==================================================
    if decision.search_type == "current_fact":

        preferred_domains = list(
            _plan_preferred_domains(prompt)
        )

        queries = [
            (
                f"{prompt} "
                f"current as of {today} "
                f"official authoritative source"
            ),
            (
                f"{prompt} "
                f"latest verified current information "
                f"as of {today}"
            ),
        ]

        return SearchPlan(
            queries=queries,
            preferred_domains=preferred_domains,
        )

    # ==================================================
    # RECENT EVENT
    # ==================================================
    if decision.search_type == "recent_event":

        dated_query = get_search_query(
            prompt
        )

        return SearchPlan(
            queries=[
                f"{dated_query} latest",
                (
                    f"{dated_query} "
                    f"latest reliable reporting"
                ),
                (
                    f"{dated_query} "
                    f"Reuters AP BBC"
                ),
            ],
            preferred_domains=[],
        )

    # ==================================================
    # REALTIME DATA
    # ==================================================
    if decision.search_type == "realtime_data":

        return SearchPlan(
            queries=[
                (
                    f"{prompt} "
                    f"current latest data "
                    f"as of {today}"
                ),
                (
                    f"{prompt} "
                    f"official current data "
                    f"{today}"
                ),
            ],
            preferred_domains=[],
        )

    # ==================================================
    # GENERAL WEB
    # ==================================================
    if decision.search_type == "general_web":

        return SearchPlan(
            queries=[
                get_search_query(prompt)
            ],
            preferred_domains=[],
        )

    # ==================================================
    # SAFE FALLBACK
    # ==================================================
    return SearchPlan(
        queries=[
            get_search_query(prompt)
        ],
        preferred_domains=[],
    )