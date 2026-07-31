from __future__ import annotations

from collections.abc import Callable

from services.model_config import ModelConfig
from services.providers.base_provider import BaseProvider
from services.providers.deepseek_provider import DeepSeekProvider
from services.providers.doubao_provider import DoubaoProvider
from services.providers.glm_provider import GLMProvider
from services.providers.kimi_provider import KimiProvider
from services.providers.openai_provider import OpenAIProvider
from services.providers.qwen_provider import QwenProvider
from services.providers.gemini_provider import GeminiProvider
from services.providers.grok_provider import GrokProvider
from services.providers.claude_provider import ClaudeProvider


class UnsupportedProviderError(ValueError):
    """Raised when no provider adapter is registered for a model."""


ProviderBuilder = Callable[[ModelConfig], BaseProvider]


class ProviderFactory:
    """Create a dedicated provider adapter from a model configuration."""

    _PROVIDERS: dict[str, ProviderBuilder] = {
        "deepseek": DeepSeekProvider,
        "zhipu": GLMProvider,
        "moonshot": KimiProvider,
        "volcengine": DoubaoProvider,
        "dashscope": QwenProvider,
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
        "xai": GrokProvider,
        "anthropic": ClaudeProvider,
    }

    @classmethod
    def create(cls, config: ModelConfig) -> BaseProvider:
        provider_class = cls._PROVIDERS.get(config.provider)

        if provider_class is None:
            raise UnsupportedProviderError(
                f"Unsupported provider adapter: {config.provider}"
            )

        return provider_class(config)
