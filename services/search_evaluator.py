from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import SEARCH_ROUTER_MODEL
from models import model_options
from services.date_service import get_now


MIN_RESULT_SCORE = 0.45
MIN_USEFUL_RESULTS = 2


def _extract_json(text: str) -> dict[str, Any] | None:
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


def _filter_relevant_results(results: list[dict]) -> list[dict]:
    """
    根据 Tavily relevance score 过滤明显低质量结果。

    没有 score 的结果暂时保留，避免误删。
    """
    useful_results = []

    for result in results:
        score = result.get("score")

        if score is None:
            useful_results.append(result)
            continue

        try:
            if float(score) >= MIN_RESULT_SCORE:
                useful_results.append(result)
        except (TypeError, ValueError):
            useful_results.append(result)

    return useful_results


def _build_results_summary(results: list[dict]) -> str:
    parts = []

    for index, result in enumerate(results[:8], start=1):
        title = result.get("title", "无标题")
        content = result.get("content", "")
        url = result.get("url", "")
        score = result.get("score", "未知")

        parts.append(
            f"结果 {index}\n"
            f"标题：{title}\n"
            f"摘要：{content[:1000]}\n"
            f"相关度：{score}\n"
            f"来源：{url}"
        )

    return "\n\n".join(parts)


def evaluate_search_results(
    user_prompt: str,
    results: list[dict],
) -> dict[str, Any]:
    """
    判断当前搜索结果是否足以回答用户问题。

    返回：
    {
        "enough": bool,
        "reason": str,
        "missing": str
    }
    """
    relevant_results = _filter_relevant_results(results)

    if not relevant_results:
        return {
            "enough": False,
            "reason": "没有找到相关度足够的搜索结果",
            "missing": "需要更直接或更权威的资料",
        }

    if len(relevant_results) < MIN_USEFUL_RESULTS:
        return {
            "enough": False,
            "reason": "有效来源数量不足",
            "missing": "需要更多独立来源",
        }

    try:
        cfg = model_options[SEARCH_ROUTER_MODEL]

        if not cfg.get("key"):
            return {
                "enough": len(relevant_results) >= MIN_USEFUL_RESULTS,
                "reason": "评估模型未配置，使用基础规则判断",
                "missing": "",
            }

        current_date = get_now().strftime("%Y-%m-%d")

        client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["key"],
        )

        results_summary = _build_results_summary(relevant_results)

        response = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是 Mango AI 的搜索结果评估器。\n"
                        "你的任务不是回答问题，而是判断现有搜索结果"
                        "是否足以可靠回答用户。\n\n"
                        f"当前日期：{current_date}\n\n"
                        "判断标准：\n"
                        "1. 结果必须真正回答用户核心问题。\n"
                        "2. 用户询问今天、当前、最新、实时信息时，"
                        "结果必须包含符合当前日期的信息。\n"
                        "3. 历史数据不能冒充今天数据。\n"
                        "4. 股票、天气、新闻、政策等时效问题，"
                        "至少需要一个日期明确且直接相关的来源。\n"
                        "5. 多条结果只是重复同一篇内容时，不能算多个可靠来源。\n"
                        "6. 如果只有模糊、历史或间接信息，应判定不足。\n"
                        "7. 如果结果已经包含直接答案和合理证据，应判定足够。\n"
                        "8. 只返回合法 JSON，不要回答用户问题。\n\n"
                        "返回格式：\n"
                        "{"
                        '"enough":true或false,'
                        '"reason":"判断原因",'
                        '"missing":"如果不足，还缺少什么；足够则为空字符串"'
                        "}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"用户问题：\n{user_prompt}\n\n"
                        f"现有搜索结果：\n{results_summary}"
                    ),
                },
            ],
            stream=False,
            temperature=0,
            max_tokens=250,
        )

        answer = response.choices[0].message.content or ""
        data = _extract_json(answer)

        if not data:
            return {
                "enough": False,
                "reason": "评估模型返回格式无效",
                "missing": "继续搜索更直接的资料",
            }

        return {
            "enough": bool(data.get("enough", False)),
            "reason": str(data.get("reason", "")).strip(),
            "missing": str(data.get("missing", "")).strip(),
        }

    except Exception as error:
        print(f"⚠️ 搜索结果评估失败：{error}")

        return {
            "enough": False,
            "reason": "搜索结果评估发生异常",
            "missing": "继续执行后续搜索",
        }