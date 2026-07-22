from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import SEARCH_ROUTER_MODEL
from models import model_options
from services.date_service import get_now


MAX_SEARCH_QUERIES = 3


def _extract_json(text: str) -> dict[str, Any] | None:
    """
    从模型返回内容中提取 JSON。

    兼容以下情况：
    1. 模型直接返回 JSON
    2. JSON 被 ```json 代码块包裹
    3. JSON 前后夹杂少量解释文字
    """
    if not text:
        return None

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)

    if not match:
        return None

    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _clean_queries(
    queries: Any,
    fallback_query: str,
) -> list[str]:
    """
    清洗搜索词：
    - 必须是字符串
    - 去除空白
    - 去重
    - 最多保留 3 条
    """
    cleaned_queries: list[str] = []
    seen: set[str] = set()

    if isinstance(queries, list):
        for query in queries:
            if not isinstance(query, str):
                continue

            query = query.strip()

            if not query:
                continue

            normalized = query.casefold()

            if normalized in seen:
                continue

            seen.add(normalized)
            cleaned_queries.append(query)

            if len(cleaned_queries) >= MAX_SEARCH_QUERIES:
                break

    if not cleaned_queries:
        cleaned_queries.append(fallback_query.strip())

    return cleaned_queries


def plan_search(prompt: str) -> list[str]:
    """
    根据用户问题生成最多 3 条互补搜索词。

    失败时自动回退为用户原始问题，
    确保联网搜索不会因为 Planner 异常而中断。
    """
    prompt = (prompt or "").strip()

    if not prompt:
        return []

    try:
        cfg = model_options[SEARCH_ROUTER_MODEL]

        if not cfg.get("key"):
            print("⚠️ Search Planner API Key 未配置，使用原始问题搜索")
            return [prompt]

        now = get_now()
        current_date = now.strftime("%Y-%m-%d")

        client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["key"],
        )

        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 Mango AI 的联网搜索规划器。\n"
                        "你的任务不是回答用户问题，而是生成高质量搜索词。\n\n"
                        f"当前日期：{current_date}\n\n"
                        "规则：\n"
                        "1. 返回最多3条互补搜索词。\n"
                        "2. 第一条应直接搜索用户的核心问题。\n"
                        "3. 后续搜索词应补充官方来源、实时数据、股票代码、"
                        "公司名称、地点、日期或英文关键词。\n"
                        "4. 涉及今天、最新、当前、实时等信息时，"
                        "必须在搜索词中加入明确日期或最新时间要求。\n"
                        "5. 涉及股票时，优先加入股票代码、交易所、"
                        "新浪财经、东方财富等行情线索。\n"
                        "6. 涉及天气时，优先加入城市、具体日期和官方气象来源。\n"
                        "7. 涉及公司新闻时，优先加入公司官网、新闻中心或公告。\n"
                        "8. 不要生成含义完全重复的搜索词。\n"
                        "9. 不要回答问题，不要解释。\n"
                        "10. 只返回合法 JSON。\n\n"
                        "返回格式：\n"
                        '{"queries":["搜索词1","搜索词2","搜索词3"]}'
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            stream=False,
            temperature=0,
            max_tokens=250,
        )

        answer = response.choices[0].message.content or ""
        data = _extract_json(answer)

        if not data:
            print("⚠️ Search Planner 返回格式无效，使用原始问题搜索")
            return [prompt]

        return _clean_queries(
            data.get("queries"),
            fallback_query=prompt,
        )

    except Exception as error:
        print(f"⚠️ Search Planner 失败：{error}")
        return [prompt]