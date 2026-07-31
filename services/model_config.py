from __future__ import annotations

from dataclasses import dataclass

from config import (
    DASHSCOPE_API_KEY,
    DEEPSEEK_API_KEY,
    DOUBAO_API_KEY,
    GEMINI_API_KEY,
    KIMI_API_KEY,
    OPENAI_API_KEY,
    ZHIPU_API_KEY,
    XAI_API_KEY,
    ANTHROPIC_API_KEY,
)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    name: str
    provider: str
    base_url: str
    model_id: str
    api_key: str | None
    supports_vision: bool = False
    uses_max_completion_tokens: bool = False


MODEL_CONFIGS: dict[str, ModelConfig] = {
    "DeepSeek": ModelConfig(
        name="DeepSeek",
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model_id="deepseek-v4-flash",
        api_key=DEEPSEEK_API_KEY,
    ),
    "GLM-4V": ModelConfig(
        name="GLM-4V",
        provider="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_id="glm-4v-plus",
        api_key=ZHIPU_API_KEY,
        supports_vision=True,
    ),
    "GLM-4": ModelConfig(
        name="GLM-4",
        provider="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        model_id="glm-4-plus",
        api_key=ZHIPU_API_KEY,
    ),
    "Kimi": ModelConfig(
        name="Kimi",
        provider="moonshot",
        base_url="https://api.moonshot.cn/v1",
        model_id="moonshot-v1-8k",
        api_key=KIMI_API_KEY,
    ),
    "Doubao-Pro": ModelConfig(
        name="Doubao-Pro",
        provider="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model_id="ep-20260415022601-jm5b7",
        api_key=DOUBAO_API_KEY,
    ),
    "Qwen": ModelConfig(
        name="Qwen",
        provider="dashscope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen-plus",
        api_key=DASHSCOPE_API_KEY,
    ),
    "Gemini": ModelConfig(
        name="Gemini",
        provider="gemini",
        base_url=(
            "https://generativelanguage.googleapis.com/"
            "v1beta/openai/"
        ),
        model_id="gemini-3.6-flash",
        api_key=GEMINI_API_KEY,
    ),
    "ChatGPT": ModelConfig(
        name="ChatGPT",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_id="gpt-5.4-mini",
        api_key=OPENAI_API_KEY,
        uses_max_completion_tokens=True,
    ),
    "Grok": ModelConfig(
        name="Grok",
        provider="xai",
        base_url="https://api.x.ai/v1",
        model_id="grok-4.5",
        api_key=XAI_API_KEY,
    ),
    "Claude": ModelConfig(
        name="Claude",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        model_id="claude-sonnet-5",
        api_key=ANTHROPIC_API_KEY,
    ),
    
}


def get_model_config(model_name: str) -> ModelConfig:
    try:
        return MODEL_CONFIGS[model_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported model: {model_name}") from exc


def get_model_names() -> list[str]:
    return list(MODEL_CONFIGS)