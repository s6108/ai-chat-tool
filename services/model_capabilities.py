from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class ModelCapability:
    """Mango Brain 模型能力元数据；评分 0～10。"""

    name: str
    provider: str
    vendor: str
    country: str

    cost_efficiency: int
    speed: int
    reasoning: int
    coding: int
    writing: int
    math: int
    vision: int
    long_context: int
    chinese: int
    english: int
    news: int
    research: int

    supports_vision: bool
    supports_native_search: bool
    supports_roundtable: bool

    preferred_tasks: tuple[str, ...]
    fallback_models: tuple[str, ...]


MODEL_CAPABILITIES: Final[dict[str, ModelCapability]] = {
    "DeepSeek": ModelCapability(
        "DeepSeek", "deepseek", "DeepSeek", "CN",
        10, 9, 10, 9, 7, 10, 0, 8, 9, 8, 4, 7,
        False, False, True,
        ("general", "utility_realtime", "general_realtime", "math", "reasoning", "coding"),
        ("Qwen", "Grok", "Claude"),
    ),
    "Qwen": ModelCapability(
        "Qwen", "dashscope", "Alibaba Cloud", "CN",
        10, 10, 8, 8, 9, 8, 0, 8, 10, 8, 4, 7,
        False, False, True,
        ("fast", "general", "writing", "translation", "summarization"),
        ("DeepSeek", "Doubao-Pro", "Kimi"),
    ),
    "Kimi": ModelCapability(
        "Kimi", "moonshot", "Moonshot AI", "CN",
        9, 8, 8, 7, 8, 7, 0, 10, 9, 8, 4, 8,
        False, False, True,
        ("long_context", "summarization", "research"),
        ("Qwen", "Claude", "Gemini"),
    ),
    "GLM-4": ModelCapability(
        "GLM-4", "zhipu", "Zhipu AI", "CN",
        9, 8, 8, 7, 8, 8, 0, 8, 9, 7, 4, 7,
        False, False, True,
        ("general", "writing", "reasoning"),
        ("Qwen", "DeepSeek"),
    ),
    "GLM-4V": ModelCapability(
        "GLM-4V", "zhipu", "Zhipu AI", "CN",
        9, 8, 8, 6, 7, 7, 9, 7, 9, 7, 4, 7,
        True, False, True,
        ("vision", "image_analysis"),
        ("Gemini", "ChatGPT"),
    ),
    "Doubao-Pro": ModelCapability(
        "Doubao-Pro", "volcengine", "ByteDance", "CN",
        9, 9, 7, 7, 9, 7, 0, 8, 10, 7, 4, 6,
        False, False, True,
        ("creative_writing", "writing", "marketing", "business_plan"),
        ("Qwen", "Claude", "Gemini"),
    ),
    "ChatGPT": ModelCapability(
        "ChatGPT", "openai", "OpenAI", "US",
        6, 8, 9, 9, 9, 9, 9, 9, 8, 10, 8, 9,
        True, False, True,
        ("coding", "reasoning", "vision", "research", "writing"),
        ("Claude", "Gemini", "Grok"),
    ),
    "Gemini": ModelCapability(
        "Gemini", "gemini", "Google", "US",
        7, 9, 9, 9, 9, 9, 10, 10, 8, 10, 9, 10,
        True, True, True,
        ("vision", "research", "news", "long_context", "reasoning"),
        ("Claude", "Grok", "ChatGPT"),
    ),
    "Grok": ModelCapability(
        "Grok", "xai", "xAI", "US",
        6, 8, 9, 9, 8, 9, 8, 9, 8, 10, 10, 9,
        True, True, True,
        ("news", "current_affairs", "coding", "research", "reasoning"),
        ("Gemini", "Claude", "DeepSeek"),
    ),
    "Claude": ModelCapability(
        "Claude", "anthropic", "Anthropic", "US",
        5, 7, 10, 10, 10, 9, 9, 10, 9, 10, 8, 10,
        True, True, True,
        ("coding", "architecture", "writing", "reasoning", "long_context", "research"),
        ("Grok", "Gemini", "DeepSeek"),
    ),
}


def get_model_capability(model_name: str) -> ModelCapability:
    try:
        return MODEL_CAPABILITIES[model_name]
    except KeyError as exc:
        raise KeyError(f"Unknown model capability: {model_name}") from exc


def supports_task(model_name: str, task_type: str) -> bool:
    return task_type in get_model_capability(model_name).preferred_tasks


def get_fallback_models(model_name: str) -> tuple[str, ...]:
    return get_model_capability(model_name).fallback_models


def get_native_search_models() -> tuple[str, ...]:
    return tuple(
        name for name, cap in MODEL_CAPABILITIES.items()
        if cap.supports_native_search
    )


def get_vision_models() -> tuple[str, ...]:
    return tuple(
        name for name, cap in MODEL_CAPABILITIES.items()
        if cap.supports_vision
    )


def rank_models_for_task(
    task_type: str,
    *,
    prefer_chinese_models: bool = True,
    require_vision: bool = False,
    require_native_search: bool = False,
) -> list[str]:
    """按质量、性价比、速度和任务偏好对模型排序。"""

    task_score_map = {
        "math": "math",
        "coding": "coding",
        "writing": "writing",
        "creative_writing": "writing",
        "reasoning": "reasoning",
        "vision": "vision",
        "long_context": "long_context",
        "news": "news",
        "research": "research",
        "general": "reasoning",
        "fast": "speed",
        "utility_realtime": "speed",
        "general_realtime": "research",
    }

    score_field = task_score_map.get(task_type, "reasoning")
    ranked: list[tuple[float, str]] = []

    for model_name, capability in MODEL_CAPABILITIES.items():
        if require_vision and not capability.supports_vision:
            continue
        if require_native_search and not capability.supports_native_search:
            continue

        quality_score = getattr(capability, score_field)
        score = (
            quality_score * 5.0
            + capability.cost_efficiency * 2.0
            + capability.speed
        )

        if task_type in capability.preferred_tasks:
            score += 8.0
        if prefer_chinese_models and capability.country == "CN":
            score += 5.0

        ranked.append((score, model_name))

    ranked.sort(reverse=True)
    return [model_name for _, model_name in ranked]