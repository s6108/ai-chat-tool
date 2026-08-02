from __future__ import annotations

from dataclasses import dataclass

from services.brain_policy import BrainPolicy, get_brain_policy
from services.model_capabilities import rank_models_for_task
from services.task_classifier import TaskInfo, classify_task


@dataclass(frozen=True)
class RouteDecision:
    model: str
    reason: str
    max_tokens: int
    temperature: float


def _select_from_policy(
    task: TaskInfo,
    policy: BrainPolicy,
) -> str:
    """
    执行 Brain Policy。

    固定政策直接返回 preferred_model；
    评分政策只允许在 policy.allowed_models 中选择。
    """
    if not policy.use_capability_ranking:
        return policy.preferred_model

    ranked = rank_models_for_task(
        task.task_type,
        prefer_chinese_models=policy.prefer_chinese_models,
        require_vision=policy.require_vision,
        require_native_search=policy.require_native_search,
    )

    for model_name in ranked:
        if model_name in policy.allowed_models:
            return model_name

    return policy.preferred_model


def choose_model_for_task(task: TaskInfo) -> RouteDecision:
    """
    Mango Brain V1.3：

    Task Classifier
        ↓
    Brain Policy Engine
        ↓
    Model Capability Center
        ↓
    RouteDecision
    """
    policy = get_brain_policy(task)
    model = _select_from_policy(task, policy)

    if policy.use_capability_ranking:
        reason = f"{policy.reason}，最终选择 {model}"
    else:
        reason = policy.reason

    return RouteDecision(
        model=model,
        reason=reason,
        max_tokens=policy.max_tokens,
        temperature=policy.temperature,
    )


def choose_auto_model(
    prompt: str,
    *,
    has_image: bool = False,
    needs_search: bool = False,
) -> RouteDecision:
    """
    保持 app.py 当前接口不变。

    needs_search 仅为兼容旧调用；搜索需求由 Task Classifier 判断。
    """
    del needs_search

    task = classify_task(
        prompt,
        has_image=has_image,
    )
    return choose_model_for_task(task)
