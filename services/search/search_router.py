from __future__ import annotations

from config import XAI_API_KEY
from services.search.base_search import BaseSearchProvider
from services.search.grok_search import GrokSearchProvider
from services.search.mango_search import MangoSearchProvider
from services.search_policy import (
    SearchDecision,
    decide_search_strategy,
)


def get_search_decision(
    model_name: str,
    task_type: str,
) -> SearchDecision:
    return decide_search_strategy(
        model_name,
        task_type,
    )


def get_search_provider(
    model_name: str,
    task_type: str,
) -> BaseSearchProvider | None:
    decision = get_search_decision(
        model_name,
        task_type,
    )

    if decision.search_type == "none":
        return None

    if decision.search_type == "mango":
        return MangoSearchProvider()

    if (
        decision.search_type == "native"
        and decision.provider == "xai"
    ):
        return GrokSearchProvider(
            api_key=XAI_API_KEY,
        )

    # Gemini 和 Claude 原生搜索尚未接入执行层。
    # 暂时回退至 Megor Search，防止运行时中断。
    return MangoSearchProvider()