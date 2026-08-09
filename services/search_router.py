from __future__ import annotations

from services.task_classifier import classify_task

from services.search_policy import decide_search_strategy


def classify_search_intent(prompt: str) -> str:
    """
    保持原有接口：
    返回 none / utility / news / general_realtime。
    """
    task = classify_task(prompt)

    mapping = {
        "utility_realtime": "utility",
        "news": "news",
        "general_realtime": "general_realtime",
    }
    return mapping.get(task.task_type, "none")


def should_search(prompt: str) -> bool:
    """所有实时事实类任务必须搜索。"""
    return classify_task(prompt).need_search

from services.search_capabilities import SEARCH_CAPABILITIES


def decide_search_provider(
    model_name: str,
    task_type: str,
):

    capability = SEARCH_CAPABILITIES.get(
        model_name
    )


    if not capability:
        return {
            "type":"mango",
            "provider":"tavily",
        }


    if task_type == "news":

        if capability.search_type == "native":

            return {
                "type":"native",
                "provider":capability.provider,
            }


    if task_type in (
        "utility_realtime",
        "general_realtime",
    ):

        return {
            "type":"mango",
            "provider":"tavily",
        }


    return {
        "type":"none",
        "provider":None,
    }
