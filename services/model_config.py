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

    # 默认文本模型
    model_id: str

    api_key: str | None

    supports_vision: bool = False
    uses_max_completion_tokens: bool = False

    # 可选：同一品牌专用视觉模型
    vision_model_id: str | None = None


MODEL_CONFIGS: dict[str, ModelConfig] = {
    "DeepSeek": ModelConfig(
        name="DeepSeek",
        provider="deepseek",
        base_url="https://api.deepseek.com",
        model_id="deepseek-v4-flash",
        api_key=DEEPSEEK_API_KEY,
        
    ),

    "GLM": ModelConfig(
        name="GLM",
        provider="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4/",

        # 普通文本 / 推理 / 圆桌 / 原生搜索
        model_id="glm-5.2",

        api_key=ZHIPU_API_KEY,

        # GLM 品牌仍然支持图片
        supports_vision=True,

        # 图片 / 多模态请求专用
        vision_model_id="glm-5v-turbo",
    ),
    
    "Kimi": ModelConfig(
        name="Kimi",
        provider="moonshot",
        base_url="https://api.moonshot.cn/v1",
        model_id="kimi-k2.5",
        api_key=KIMI_API_KEY,
        supports_vision=True,
    ),
    "Doubao-Pro": ModelConfig(
        name="Doubao-Pro",
        provider="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model_id="ep-20260415022601-jm5b7",
        api_key=DOUBAO_API_KEY,
        supports_vision=True,
    ),
    "Qwen": ModelConfig(
        name="Qwen",
        provider="dashscope",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_id="qwen3.6-flash",
        api_key=DASHSCOPE_API_KEY,
        supports_vision=True,
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
        supports_vision=True,
    ),
    "ChatGPT": ModelConfig(
        name="ChatGPT",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_id="gpt-5.4-mini",
        api_key=OPENAI_API_KEY,
        supports_vision=True,
        uses_max_completion_tokens=True,
    ),
    "Grok": ModelConfig(
        name="Grok",
        provider="xai",
        base_url="https://api.x.ai/v1",
        model_id="grok-4.5",
        api_key=XAI_API_KEY,
        supports_vision=True,
    ),
    "Claude": ModelConfig(
        name="Claude",
        provider="anthropic",
        base_url="https://api.anthropic.com",
        model_id="claude-sonnet-5",
        api_key=ANTHROPIC_API_KEY,
        supports_vision=True,
    ),
    
}


def get_model_config(model_name: str) -> ModelConfig:
    try:
        return MODEL_CONFIGS[model_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported model: {model_name}") from exc


def get_model_names() -> list[str]:
    return list(MODEL_CONFIGS)