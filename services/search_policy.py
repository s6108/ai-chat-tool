from __future__ import annotations

from dataclasses import dataclass

from services.search_capabilities import get_search_capability


@dataclass(frozen=True)
class SearchDecision:

    search_type: str
    provider: str
    reason: str



def decide_search_strategy(
    model_name: str,
    task_type: str,
) -> SearchDecision:
    """
    决定搜索来源。

    第一阶段：
    所有需要联网的任务统一使用 Mango Search。
    模型只负责分析和生成最终回答。
    """

    searchable_task_types = {
        "news",
        "utility_realtime",
        "general_realtime",
        "research",
    }

    if task_type in searchable_task_types:
        return SearchDecision(
            search_type="mango",
            provider="mango",
            reason="第一阶段所有联网任务统一使用 Mango Search",
        )

    return SearchDecision(
        search_type="none",
        provider="none",
        reason="当前任务不需要联网搜索",
    )