from __future__ import annotations

from services.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class OpenAIProvider(OpenAICompatibleProvider):
    """OpenAI adapter with model-specific token parameter handling."""
