from __future__ import annotations

from services.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class DeepSeekProvider(OpenAICompatibleProvider):
    """DeepSeek adapter using its OpenAI-compatible chat API."""
