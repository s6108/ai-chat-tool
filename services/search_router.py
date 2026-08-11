from __future__ import annotations

from services.task_classifier import classify_task


def classify_search_intent(
    prompt: str,
) -> str:
    """
    保持旧接口兼容。

    是否联网由 AI Freshness Layer 决定。
    task_type 只用于描述搜索类型。
    """

    task = classify_task(prompt)

    if not task.need_search:
        return "none"

    mapping = {
        "utility_realtime": "utility",
        "news": "news",
        "general_realtime": "general_realtime",
    }

    return mapping.get(
        task.task_type,
        "general_realtime",
    )


def should_search(
    prompt: str,
) -> bool:
    """
    AI 判断是否需要联网。

    不再依赖关键词决定是否搜索。
    """
    task = classify_task(prompt)

    return task.need_search


def decide_search_provider(
    model_name: str,
    task_type: str,
):
    """
    第一阶段所有需要联网的任务
    统一使用 Megor Search / Tavily。

    model_name 和 task_type 暂时保留，
    用于兼容现有调用接口。
    """

    del model_name
    del task_type

    return {
        "type": "mango",
        "provider": "tavily",
    }