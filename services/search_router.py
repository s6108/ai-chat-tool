from __future__ import annotations

from services.task_classifier import classify_task


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
