from __future__ import annotations

from services.model_config import ModelConfig
from services.providers.base_provider import BaseProvider
from services.providers.openai_compatible_provider import OpenAICompatibleProvider


class UnsupportedProviderError(ValueError):
    """Raised when no provider adapter is registered for a model."""


class ProviderFactory:
    """Create the provider adapter required by a model configuration."""

    _OPENAI_COMPATIBLE_PROVIDERS = {
        "deepseek",
        "zhipu",
        "moonshot",
        "volcengine",
        "dashscope",
        "openai",
    }

    @classmethod
    def create(cls, config: ModelConfig) -> BaseProvider:
        if config.provider in cls._OPENAI_COMPATIBLE_PROVIDERS:
            return OpenAICompatibleProvider(config)

        raise UnsupportedProviderError(
            f"Unsupported provider adapter: {config.provider}"
        )
