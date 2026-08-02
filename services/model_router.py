from __future__ import annotations

from dataclasses import dataclass

from services.task_classifier import TaskInfo, classify_task


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    max_tokens: int
    temperature: float


def choose_model_for_task(task: TaskInfo) -> RouteDecision:
    """
    Mango Brain V1.1：
    准确性优先；质量相近时优先中国模型、低成本模型和更快模型。
    """
    routes: dict[str, RouteDecision] = {
        "vision": RouteDecision(
            model="GLM-4V",
            reason="图片识别任务，优先使用中国视觉模型",
            max_tokens=1200,
            temperature=0.4,
        ),
        "utility_realtime": RouteDecision(
            model="DeepSeek",
            reason="天气、股票、汇率等低成本实时查询",
            max_tokens=1000,
            temperature=0.2,
        ),
        "news": RouteDecision(
            model="Grok",
            reason="新闻、政治或国际时事，使用国际模型",
            max_tokens=1400,
            temperature=0.3,
        ),
        "general_realtime": RouteDecision(
            model="DeepSeek",
            reason="普通实时资料整合，优先使用低成本中国模型",
            max_tokens=1100,
            temperature=0.3,
        ),
        "math": RouteDecision(
            model="DeepSeek",
            reason="数学、计算或逻辑推理任务",
            max_tokens=1400,
            temperature=0.2,
        ),
        "long_context": RouteDecision(
            model="Kimi",
            reason="超长文本或完整文档处理",
            max_tokens=1600,
            temperature=0.4,
        ),
        "creative_writing": RouteDecision(
            model="Doubao-Pro",
            reason="长篇创意、营销或商业写作",
            max_tokens=1700,
            temperature=0.75,
        ),
        "writing": RouteDecision(
            model="Qwen",
            reason="中文写作、总结、改写或润色",
            max_tokens=1300,
            temperature=0.65,
        ),
        "reasoning": RouteDecision(
            model="DeepSeek",
            reason="分析、推理、规划或决策任务",
            max_tokens=1300,
            temperature=0.3,
        ),
        "fast": RouteDecision(
            model="Qwen",
            reason="快速轻量任务",
            max_tokens=800,
            temperature=0.5,
        ),
        "general": RouteDecision(
            model="DeepSeek",
            reason="普通常识或综合问答",
            max_tokens=1100,
            temperature=0.45,
        ),
    }

    if task.task_type == "coding":
        if task.complexity == "high":
            return RouteDecision(
                model="Claude",
                reason="复杂代码、系统设计或大型重构任务",
                max_tokens=1800,
                temperature=0.2,
            )
        return RouteDecision(
            model="DeepSeek",
            reason="普通编程或调试任务，优先使用中国模型",
            max_tokens=1400,
            temperature=0.2,
        )

    return routes.get(task.task_type, routes["general"])


def choose_auto_model(
    prompt: str,
    *,
    has_image: bool = False,
    needs_search: bool = False,
) -> RouteDecision:
    """
    保持 app.py 现有接口不变。
    needs_search 参数仅用于兼容旧调用；真实搜索需求由 Task Classifier 决定。
    """
    del needs_search

    task = classify_task(
        prompt,
        has_image=has_image,
    )
    return choose_model_for_task(task)