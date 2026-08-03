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

    当前只负责决策，不执行搜索。
    """

    capability = get_search_capability(model_name)
    if capability is None:
        return SearchDecision(
            search_type="mango",
            provider="tavily",
            reason="未知模型，默认使用 Mango Search",
        )


    # 新闻类优先国际模型原生搜索
    if task_type == "news":

        if capability.search_type == "native":

            return SearchDecision(
                search_type="native",
                provider=capability.provider,
                reason=(
                    "新闻和国际时事优先使用模型原生搜索"
                ),
            )


    # 普通实时数据继续 Mango Search
    if task_type in (
        "utility_realtime",
        "general_realtime",
    ):

        return SearchDecision(
            search_type="mango",
            provider="mango",
            reason=(
                "天气、股票、汇率等数据使用 Mango Search "
                "降低成本"
            ),
        )


    # 研究类
    if task_type == "research":

        if capability.search_type == "native":

            return SearchDecision(
                search_type="native",
                provider=capability.provider,
                reason=(
                    "研究类任务优先使用原生搜索"
                ),
            )


    # 默认
    return SearchDecision(
        search_type="none",
        provider="none",
        reason="当前任务不需要搜索",
    )